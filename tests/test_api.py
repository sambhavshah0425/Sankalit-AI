import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app, UPLOADS_DIR
from app.rag.embedder import EXPECTED_EMBEDDING_DIM
from app.rag.vector_store import initialize_database
from app.security.deps import get_current_user
from tests.helpers import create_sample_docx, create_sample_pdf


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        # Override get_current_user with an active SUPER_ADMIN context for basic API tests
        app.dependency_overrides[get_current_user] = lambda: {
            "id": 1,
            "username": "admin",
            "email": "admin@sankalit.local",
            "full_name": "System Administrator",
            "roles": ["SUPER_ADMIN"],
            "permissions": {
                "user:read", "user:create", "user:update", "user:delete",
                "role:read", "role:assign", "department:read", "department:manage",
                "document:read", "document:upload", "document:delete", "document:manage_permissions",
                "rag:query", "audit:read", "system:config"
            },
            "departments": [],
            "is_active": True,
            "is_superuser": True
        }
        self.client = TestClient(app)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def test_root_endpoint(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"application": "Sankalit Intelligence", "status": "running"})

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "healthy", "application": "Sankalit Intelligence"})

    @patch("httpx.AsyncClient.get")
    def test_health_ollama_mocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        async def fake_get(*args, **kwargs):
            return mock_resp

        mock_get.side_effect = fake_get

        resp = self.client.get("/health/ollama")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "connected")

    @patch("httpx.AsyncClient.post")
    def test_chat_endpoint_mocked(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "response": "Hello from local Qwen!",
            "done": True
        }

        async def fake_post(*args, **kwargs):
            return mock_resp

        mock_post.side_effect = fake_post

        resp = self.client.post("/chat", json={"message": "Hello"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["response"], "Hello from local Qwen!")

    def test_upload_unsupported_file_extension(self):
        file_bytes = io.BytesIO(b"System command script")
        resp = self.client.post(
            "/documents/upload",
            files={"file": ("malicious.sh", file_bytes, "application/x-sh")}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file format", resp.json()["detail"])

    @patch("app.main.MAX_UPLOAD_SIZE_BYTES", 100)  # limit to 100 bytes for test
    def test_upload_file_too_large(self):
        file_bytes = io.BytesIO(b"A" * 500)
        resp = self.client.post(
            "/documents/upload",
            files={"file": ("large_doc.pdf", file_bytes, "application/pdf")}
        )
        self.assertEqual(resp.status_code, 413)
        self.assertIn("File exceeds maximum allowed size", resp.json()["detail"])

    @patch("app.rag.ingestion.embed_chunks")
    def test_upload_and_crud_lifecycle(self, mock_embed_chunks):
        dummy_embedding = [0.05] * EXPECTED_EMBEDDING_DIM
        mock_embed_chunks.side_effect = lambda chunks, batch_size=16: [
            {**c, "embedding": dummy_embedding} for c in chunks
        ]

        # 1. Create and upload DOCX
        docx_file = create_sample_docx(
            "Sankalit Consultant offers bespoke data architectures and AI systems.",
            "test_crud.docx",
            self.dir_path
        )

        with open(docx_file, "rb") as f:
            upload_resp = self.client.post(
                "/documents/upload",
                files={"file": ("test_crud.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            )

        self.assertEqual(upload_resp.status_code, 201)
        data = upload_resp.json()
        doc_id = data["document_id"]
        self.assertEqual(data["ingestion_status"], "success")

        # 2. Get document by ID
        get_resp = self.client.get(f"/documents/{doc_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["id"], doc_id)

        # 3. List documents
        list_resp = self.client.get("/documents")
        self.assertEqual(list_resp.status_code, 200)
        doc_ids = [d["id"] for d in list_resp.json()["documents"]]
        self.assertIn(doc_id, doc_ids)

        # 4. Upload duplicate file
        with open(docx_file, "rb") as f:
            dup_resp = self.client.post(
                "/documents/upload",
                files={"file": ("test_crud.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            )
        self.assertEqual(dup_resp.status_code, 201)
        self.assertEqual(dup_resp.json()["ingestion_status"], "duplicate_skipped")
        self.assertEqual(dup_resp.json()["document_id"], doc_id)

        # 5. Delete document
        del_resp = self.client.delete(f"/documents/{doc_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["deleted"])

        # 6. Verify 404 after deletion
        get_again = self.client.get(f"/documents/{doc_id}")
        self.assertEqual(get_again.status_code, 404)

    @patch("app.main.answer_query_async")
    def test_rag_query_endpoint(self, mock_answer_async):
        async def fake_answer(query, top_k=4, min_score=0.25, **kwargs):
            return {
                "answer": "Sankalit uses local AI [Source: intro.pdf, Chunk 0].",
                "sources": [{"filename": "intro.pdf", "chunk_index": 0, "similarity": 0.89}],
                "retrieved_chunks": [],
                "model": "qwen3:1.7b",
                "retrieval_status": "success"
            }

        mock_answer_async.side_effect = fake_answer

        resp = self.client.post(
            "/rag/query",
            json={"query": "What does Sankalit use?", "top_k": 3, "min_score": 0.3}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("local AI", body["answer"])
        self.assertEqual(body["retrieval_status"], "success")
        self.assertEqual(len(body["sources"]), 1)

    def test_rag_stats_endpoint(self):
        resp = self.client.get("/rag/stats")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("total_indexed_documents", body)
        self.assertIn("total_stored_chunks", body)
        self.assertIn("embedding_model", body)
        self.assertEqual(body["embedding_dimensions"], 768)
        self.assertIn("chat_model", body)


if __name__ == "__main__":
    unittest.main()


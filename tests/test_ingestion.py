import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.rag.embedder import EXPECTED_EMBEDDING_DIM
from app.rag.ingestion import ingest_document, calculate_content_hash
from app.rag.vector_store import (
    get_database_stats,
    get_document,
    initialize_database,
)
from tests.helpers import create_sample_docx, create_sample_pdf


class TestIngestion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.db_path = self.dir_path / "test_ingest.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.rag.ingestion.embed_chunks")
    def test_successful_docx_ingestion(self, mock_embed_chunks):
        dummy_embedding = [0.05] * EXPECTED_EMBEDDING_DIM

        def fake_embed(chunks, batch_size=16):
            return [{**c, "embedding": dummy_embedding} for c in chunks]

        mock_embed_chunks.side_effect = fake_embed

        sample_text = "Sankalit Intelligence provides enterprise search and local LLM agents."
        docx_path = create_sample_docx(sample_text, "company_intro.docx", self.dir_path)

        result = ingest_document(str(docx_path), db_path=self.db_path)

        self.assertIn("document_id", result)
        self.assertEqual(result["filename"], "company_intro.docx")
        self.assertEqual(result["file_type"], ".docx")
        self.assertEqual(result["ingestion_status"], "success")
        self.assertFalse(result["duplicate_status"])
        self.assertEqual(result["total_chunks"], 1)
        self.assertEqual(result["embedded_chunks"], 1)

        # Verify persisted in database
        doc = get_document(result["document_id"], db_path=self.db_path)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["character_count"], result["character_count"])

    @patch("app.rag.ingestion.embed_chunks")
    def test_duplicate_document_skips_embedding(self, mock_embed_chunks):
        dummy_embedding = [0.05] * EXPECTED_EMBEDDING_DIM
        mock_embed_chunks.side_effect = lambda chunks, batch_size=16: [
            {**c, "embedding": dummy_embedding} for c in chunks
        ]

        text = "Sankalit Security Protocol Policy document."
        docx_path = create_sample_docx(text, "policy.docx", self.dir_path)

        # First ingestion
        res1 = ingest_document(str(docx_path), db_path=self.db_path)
        self.assertEqual(res1["ingestion_status"], "success")
        self.assertFalse(res1["duplicate_status"])
        self.assertEqual(mock_embed_chunks.call_count, 1)

        # Second ingestion with identical content
        res2 = ingest_document(str(docx_path), db_path=self.db_path)
        self.assertEqual(res2["ingestion_status"], "duplicate_skipped")
        self.assertTrue(res2["duplicate_status"])
        self.assertEqual(res2["document_id"], res1["document_id"])
        self.assertEqual(res2["embedded_chunks"], 0)

        # embed_chunks should NOT have been called a second time
        self.assertEqual(mock_embed_chunks.call_count, 1)

    def test_unsupported_file_rejection(self):
        txt_path = self.dir_path / "notes.txt"
        txt_path.write_text("plain text", encoding="utf-8")

        with self.assertRaises(ValueError):
            ingest_document(str(txt_path), db_path=self.db_path)

    def test_nonexistent_file_rejection(self):
        missing = self.dir_path / "missing.docx"
        with self.assertRaises(FileNotFoundError):
            ingest_document(str(missing), db_path=self.db_path)

    @patch("app.rag.ingestion.embed_chunks")
    def test_failed_embedding_leaves_no_orphaned_records(self, mock_embed_chunks):
        mock_embed_chunks.side_effect = RuntimeError("Embedding service connection timed out")

        text = "Important Sankalit financial audit notes."
        docx_path = create_sample_docx(text, "audit.docx", self.dir_path)

        with self.assertRaises(RuntimeError):
            ingest_document(str(docx_path), db_path=self.db_path)

        stats = get_database_stats(self.db_path)
        self.assertEqual(stats["documents"], 0)
        self.assertEqual(stats["chunks"], 0)


if __name__ == "__main__":
    unittest.main()


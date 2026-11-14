import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.rag.embedder import EXPECTED_EMBEDDING_DIM
from app.rag.vector_store import initialize_database, save_document
from app.security.document_access import (
    VISIBILITY_DEPARTMENT,
    VISIBILITY_PUBLIC,
    VISIBILITY_RESTRICTED,
)
from app.security.rbac import ROLE_SUPER_ADMIN, ROLE_EMPLOYEE
from app.services import auth_service, department_service
from tests.helpers import create_sample_docx


class TestSecurityAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.db_path = self.dir_path / "test_api_sec.db"
        initialize_database(self.db_path)

        # Patch DATABASE_PATH in vector_store and config to use temporary test DB
        self.patcher1 = patch("app.rag.vector_store.DATABASE_PATH", self.db_path)
        self.patcher2 = patch("app.config.DATABASE_PATH", self.db_path)
        self.patcher1.start()
        self.patcher2.start()

        self.client = TestClient(app)

        # 1. Bootstrap Super Admin
        self.super_admin = auth_service.register_user(
            username="super_admin",
            email="super@sankalit.local",
            password="SuperPassword123",
            db_path=self.db_path
        )

        # 2. Get Department IDs
        depts = department_service.list_departments(db_path=self.db_path)
        self.hr_dept = next(d for d in depts if d["name"] == "HR")
        self.it_dept = next(d for d in depts if d["name"] == "IT")

        # 3. Create HR Employee
        self.hr_user = auth_service.register_user(
            username="hr_clerk",
            email="hr@sankalit.local",
            password="HrPassword123",
            requested_roles=[ROLE_EMPLOYEE],
            department_ids=[self.hr_dept["id"]],
            actor=self.super_admin,
            db_path=self.db_path
        )

        # 4. Create IT Employee
        self.it_user = auth_service.register_user(
            username="it_tech",
            email="it@sankalit.local",
            password="ItPassword123",
            requested_roles=[ROLE_EMPLOYEE],
            department_ids=[self.it_dept["id"]],
            actor=self.super_admin,
            db_path=self.db_path
        )

        # Obtain JWT tokens for each user
        _, self.admin_token, self.admin_refresh = auth_service.authenticate_user(
            "super_admin", "SuperPassword123", db_path=self.db_path
        )
        _, self.hr_token, self.hr_refresh = auth_service.authenticate_user(
            "hr_clerk", "HrPassword123", db_path=self.db_path
        )
        _, self.it_token, self.it_refresh = auth_service.authenticate_user(
            "it_tech", "ItPassword123", db_path=self.db_path
        )

        # Populate test documents with distinct dummy embeddings
        # HR doc: high along dim 0
        vec_hr = [0.0] * EXPECTED_EMBEDDING_DIM
        vec_hr[0] = 1.0

        # IT doc: high along dim 1
        vec_it = [0.0] * EXPECTED_EMBEDDING_DIM
        vec_it[1] = 1.0

        self.hr_doc_id = save_document(
            filename="confidential_salaries.docx",
            file_type=".docx",
            content_hash="hash_hr_salaries",
            character_count=150,
            chunks=[{"chunk_index": 0, "text": "Executive base salary: Partner gets 60 LPA.", "embedding": vec_hr}],
            owner_id=self.hr_user["id"],
            visibility=VISIBILITY_DEPARTMENT,
            department_ids=[self.hr_dept["id"]],
            db_path=self.db_path
        )

        self.it_doc_id = save_document(
            filename="firewall_credentials.docx",
            file_type=".docx",
            content_hash="hash_it_creds",
            character_count=150,
            chunks=[{"chunk_index": 0, "text": "Palo Alto firewall root admin password is encrypted.", "embedding": vec_it}],
            owner_id=self.it_user["id"],
            visibility=VISIBILITY_DEPARTMENT,
            department_ids=[self.it_dept["id"]],
            db_path=self.db_path
        )

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.temp_dir.cleanup()

    def test_auth_login_and_me_endpoints(self):
        # 1. Successful login
        resp = self.client.post(
            "/auth/login",
            json={"username": "hr_clerk", "password": "HrPassword123"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

        # 2. GET /auth/me with Bearer token
        me_resp = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {data['access_token']}"}
        )
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.json()
        self.assertEqual(me_data["username"], "hr_clerk")
        self.assertIn("EMPLOYEE", me_data["roles"])
        dept_names = [d["name"] for d in me_data["departments"]]
        self.assertIn("HR", dept_names)

        # 3. GET /auth/me without token -> 401
        unauth_resp = self.client.get("/auth/me")
        self.assertEqual(unauth_resp.status_code, 401)

    def test_cross_department_document_access_via_api(self):
        # HR user can view HR document
        resp_hr_view = self.client.get(
            f"/documents/{self.hr_doc_id}",
            headers={"Authorization": f"Bearer {self.hr_token}"}
        )
        self.assertEqual(resp_hr_view.status_code, 200)
        self.assertEqual(resp_hr_view.json()["filename"], "confidential_salaries.docx")

        # IT user attempting to view HR document receives 404 (prevents ID enumeration)
        resp_it_view_hr = self.client.get(
            f"/documents/{self.hr_doc_id}",
            headers={"Authorization": f"Bearer {self.it_token}"}
        )
        self.assertEqual(resp_it_view_hr.status_code, 404)

        # IT user attempting to delete HR document receives 403 Forbidden
        resp_it_del_hr = self.client.delete(
            f"/documents/{self.hr_doc_id}",
            headers={"Authorization": f"Bearer {self.it_token}"}
        )
        self.assertEqual(resp_it_del_hr.status_code, 403)

    @patch("app.rag.retriever.generate_single_embedding")
    @patch("httpx.AsyncClient.post")
    def test_cross_department_rag_retrieval_isolation(self, mock_llm_post, mock_embed):
        # Query embedding closer to HR salary document (dim 0 = 1.0)
        vec_query = [0.0] * EXPECTED_EMBEDDING_DIM
        vec_query[0] = 1.0
        mock_embed.return_value = vec_query

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "response": "Partner base salary is 60 LPA [Source: confidential_salaries.docx, Chunk 0]."
        }

        async def fake_llm(*args, **kwargs):
            return mock_resp

        mock_llm_post.side_effect = fake_llm

        # 1. HR User queries salary policy -> Authorized, answers with citations
        hr_rag_resp = self.client.post(
            "/rag/query",
            json={"query": "What is the partner salary?", "top_k": 3, "min_score": 0.25, "detailed": True},
            headers={"Authorization": f"Bearer {self.hr_token}"}
        )
        self.assertEqual(hr_rag_resp.status_code, 200)
        hr_body = hr_rag_resp.json()
        self.assertEqual(hr_body["retrieval_status"], "success")
        self.assertIn("confidential_salaries.docx", hr_body["sources"][0]["filename"])

        # 2. IT User queries the exact same question ->
        # Because IT user is NOT in HR department, the SQL filter returns 0 chunks.
        # Short-circuits immediately to insufficient context!
        it_rag_resp = self.client.post(
            "/rag/query",
            json={"query": "What is the partner salary?", "top_k": 3, "min_score": 0.25, "detailed": True},
            headers={"Authorization": f"Bearer {self.it_token}"}
        )
        self.assertEqual(it_rag_resp.status_code, 200)
        it_body = it_rag_resp.json()
        self.assertEqual(it_body["retrieval_status"], "insufficient_context")
        self.assertEqual(it_body["sources"], [])
        self.assertIn("do not contain enough information", it_body["answer"])

    def test_admin_and_role_escalation_via_api(self):
        # Normal employee attempting to create a user -> 403 Forbidden
        emp_create_resp = self.client.post(
            "/users",
            json={
                "username": "new_staff",
                "email": "staff@sankalit.local",
                "password": "NewStaffPass123"
            },
            headers={"Authorization": f"Bearer {self.hr_token}"}
        )
        self.assertEqual(emp_create_resp.status_code, 403)

        # Super Admin creating user -> 201 Created
        sa_create_resp = self.client.post(
            "/users",
            json={
                "username": "new_staff",
                "email": "staff@sankalit.local",
                "password": "NewStaffPass123",
                "roles": ["EMPLOYEE"]
            },
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(sa_create_resp.status_code, 201)


if __name__ == "__main__":
    unittest.main()

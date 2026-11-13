import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.rag.embedder import EXPECTED_EMBEDDING_DIM
from app.rag.ingestion import ingest_document
from app.rag.rag_pipeline import answer_query
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.vector_store import (
    get_database_stats,
    get_document,
    initialize_database,
    list_documents,
    search_similar_chunks,
)
from app.security.document_access import (
    VISIBILITY_COMPANY,
    VISIBILITY_DEPARTMENT,
    VISIBILITY_PUBLIC,
    VISIBILITY_RESTRICTED,
    can_user_manage_document,
    can_user_read_document,
    get_authorized_document_ids,
)
from app.security.rbac import (
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_EMPLOYEE,
    ROLE_VIEWER,
)
from app.services import (
    auth_service,
    department_service,
    document_service,
    user_service,
)
from tests.helpers import create_sample_docx


class TestDocumentSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.db_path = self.dir_path / "test_doc_sec.db"
        initialize_database(self.db_path)

        # 1. Root Admin
        self.super_admin = auth_service.register_user(
            username="super_admin",
            email="super@sankalit.local",
            password="SuperPassword123",
            db_path=self.db_path
        )

        # 2. Departments
        depts = department_service.list_departments(db_path=self.db_path)
        self.hr_dept = next(d for d in depts if d["name"] == "HR")
        self.it_dept = next(d for d in depts if d["name"] == "IT")

        # 3. HR Employee
        self.hr_user = auth_service.register_user(
            username="hr_bob",
            email="bob@sankalit.local",
            password="BobPassword123",
            requested_roles=[ROLE_EMPLOYEE],
            department_ids=[self.hr_dept["id"]],
            actor=self.super_admin,
            db_path=self.db_path
        )

        # 4. IT Employee
        self.it_user = auth_service.register_user(
            username="it_alice",
            email="alice@sankalit.local",
            password="AlicePassword123",
            requested_roles=[ROLE_EMPLOYEE],
            department_ids=[self.it_dept["id"]],
            actor=self.super_admin,
            db_path=self.db_path
        )

        # Mock embedding vectors
        dummy_embedding = [0.05] * EXPECTED_EMBEDDING_DIM

        with patch("app.rag.ingestion.embed_chunks") as mock_embed:
            mock_embed.side_effect = lambda chunks, batch_size=16: [
                {**c, "embedding": dummy_embedding} for c in chunks
            ]

            # Ingest HR Department Document
            hr_file = create_sample_docx(
                "Confidential HR Compensation Matrix: Senior Consultant base 35 LPA.",
                "hr_salaries.docx",
                self.dir_path
            )
            self.hr_doc = ingest_document(
                str(hr_file),
                owner_id=self.hr_user["id"],
                visibility=VISIBILITY_DEPARTMENT,
                department_ids=[self.hr_dept["id"]],
                db_path=self.db_path
            )

            # Ingest IT Department Document
            it_file = create_sample_docx(
                "IT Infrastructure Disaster Recovery: Root database encryption keys stored in HSM.",
                "it_recovery.docx",
                self.dir_path
            )
            self.it_doc = ingest_document(
                str(it_file),
                owner_id=self.it_user["id"],
                visibility=VISIBILITY_DEPARTMENT,
                department_ids=[self.it_dept["id"]],
                db_path=self.db_path
            )

            # Ingest Public Document
            public_file = create_sample_docx(
                "Sankalit Public Overview: Consulting in acoustics, lighting, and MEP engineering.",
                "public_brochure.docx",
                self.dir_path
            )
            self.public_doc = ingest_document(
                str(public_file),
                owner_id=self.super_admin["id"],
                visibility=VISIBILITY_PUBLIC,
                db_path=self.db_path
            )

            # Ingest Restricted Document
            restricted_file = create_sample_docx(
                "Board of Directors Strategic Merger & Acquisition Targets 2027.",
                "board_minutes.docx",
                self.dir_path
            )
            self.restricted_doc = ingest_document(
                str(restricted_file),
                owner_id=self.super_admin["id"],
                visibility=VISIBILITY_RESTRICTED,
                db_path=self.db_path
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cross_department_isolation(self):
        hr_accessible = get_authorized_document_ids(self.hr_user, db_path=self.db_path)
        it_accessible = get_authorized_document_ids(self.it_user, db_path=self.db_path)

        # HR user can access HR doc & Public doc, but NOT IT doc or Restricted doc
        self.assertIn(self.hr_doc["document_id"], hr_accessible)
        self.assertIn(self.public_doc["document_id"], hr_accessible)
        self.assertNotIn(self.it_doc["document_id"], hr_accessible)
        self.assertNotIn(self.restricted_doc["document_id"], hr_accessible)

        # IT user can access IT doc & Public doc, but NOT HR doc or Restricted doc
        self.assertIn(self.it_doc["document_id"], it_accessible)
        self.assertIn(self.public_doc["document_id"], it_accessible)
        self.assertNotIn(self.hr_doc["document_id"], it_accessible)
        self.assertNotIn(self.restricted_doc["document_id"], it_accessible)

        # Super Admin can access ALL documents
        sa_accessible = get_authorized_document_ids(self.super_admin, db_path=self.db_path)
        self.assertIn(self.hr_doc["document_id"], sa_accessible)
        self.assertIn(self.it_doc["document_id"], sa_accessible)
        self.assertIn(self.public_doc["document_id"], sa_accessible)
        self.assertIn(self.restricted_doc["document_id"], sa_accessible)

    def test_unauthorized_chunks_never_queried_or_retrieved(self):
        """
        CRITICAL RETRIEVAL VERIFICATION:
        Ensure that when an IT user queries, the database query filters out HR documents at the SQL layer.
        """
        it_allowed_ids = get_authorized_document_ids(self.it_user, db_path=self.db_path)

        # Query embedding matching all dummy chunks
        dummy_query_vec = [0.05] * EXPECTED_EMBEDDING_DIM

        # Retrieve chunks filtered by IT user's allowed IDs
        chunks = search_similar_chunks(
            query_embedding=dummy_query_vec,
            top_k=10,
            allowed_document_ids=it_allowed_ids,
            db_path=self.db_path
        )

        retrieved_doc_ids = {c["document_id"] for c in chunks}
        retrieved_filenames = {c["filename"] for c in chunks}

        # IT user must see IT and Public docs ONLY
        self.assertIn(self.it_doc["document_id"], retrieved_doc_ids)
        self.assertIn("it_recovery.docx", retrieved_filenames)

        # MUST NEVER CONTAIN HR OR RESTRICTED DOCS!
        self.assertNotIn(self.hr_doc["document_id"], retrieved_doc_ids)
        self.assertNotIn("hr_salaries.docx", retrieved_filenames)
        self.assertNotIn(self.restricted_doc["document_id"], retrieved_doc_ids)
        self.assertNotIn("board_minutes.docx", retrieved_filenames)

    @patch("app.rag.rag_pipeline.retrieve_relevant_chunks")
    def test_rag_query_with_insufficient_permission_short_circuits(self, mock_retrieve):
        # When user has 0 allowed documents
        mock_retrieve.return_value = []

        res = answer_query(
            query="What are the executive salaries?",
            allowed_document_ids=[],
            db_path=self.db_path
        )

        self.assertEqual(res["retrieval_status"], "insufficient_context")
        self.assertEqual(res["sources"], [])
        self.assertIn("do not contain enough information", res["answer"])

    def test_explicit_document_permission_grant(self):
        # Initially, IT user cannot access Restricted Board doc
        self.assertFalse(can_user_read_document(self.it_user, self.restricted_doc["document_id"], db_path=self.db_path))

        # Super Admin grants explicit read access to IT user
        document_service.update_document_access_permissions(
            user=self.super_admin,
            document_id=self.restricted_doc["document_id"],
            permissions_list=[{"user_id": self.it_user["id"], "permission_type": "read"}],
            db_path=self.db_path
        )

        # Now IT user can access the Restricted document
        self.assertTrue(can_user_read_document(self.it_user, self.restricted_doc["document_id"], db_path=self.db_path))
        it_ids = get_authorized_document_ids(self.it_user, db_path=self.db_path)
        self.assertIn(self.restricted_doc["document_id"], it_ids)

    def test_document_listing_isolation(self):
        # List documents for HR user
        hr_docs = document_service.get_user_accessible_documents(self.hr_user, db_path=self.db_path)
        hr_filenames = [d["filename"] for d in hr_docs]

        self.assertIn("hr_salaries.docx", hr_filenames)
        self.assertIn("public_brochure.docx", hr_filenames)
        self.assertNotIn("it_recovery.docx", hr_filenames)
        self.assertNotIn("board_minutes.docx", hr_filenames)

    def test_document_deletion_authorization(self):
        # HR user cannot delete IT document
        with self.assertRaises(PermissionError):
            document_service.delete_user_accessible_document(
                user=self.hr_user,
                document_id=self.it_doc["document_id"],
                db_path=self.db_path
            )

        # IT user (owner) CAN delete IT document
        deleted = document_service.delete_user_accessible_document(
            user=self.it_user,
            document_id=self.it_doc["document_id"],
            db_path=self.db_path
        )
        self.assertTrue(deleted)


if __name__ == "__main__":
    unittest.main()


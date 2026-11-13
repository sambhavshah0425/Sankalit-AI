"""Tests for Domain-Aware Retrieval, Prompt Injection Isolation, and RAG Pipeline:
Cross-domain search, metadata filtering, and adversarial prompt handling.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.rag.vector_store import initialize_database, save_document
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.rag_pipeline import answer_query, INSUFFICIENT_CONTEXT_MESSAGE


class TestDomainAwareRAG(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_domain_rag.db"
        initialize_database(self.db_path)

        # Ingest two distinct domain documents
        mock_embedding_hr = [0.1] * 768
        mock_embedding_airport = [0.2] * 768

        self.hr_doc_id = save_document(
            filename="HR_Leave_2026.pdf",
            file_type=".pdf",
            content_hash="hr_hash_123",
            character_count=100,
            chunks=[{
                "chunk_index": 0,
                "text": "HR Leave Policy: Annual leave is 24 days per calendar year.",
                "embedding": mock_embedding_hr
            }],
            domain_id=7,  # HR domain
            document_type="policy",
            db_path=self.db_path
        )

        self.airport_doc_id = save_document(
            filename="Airport_BHS_Spec.pdf",
            file_type=".pdf",
            content_hash="airport_hash_123",
            character_count=120,
            chunks=[{
                "chunk_index": 0,
                "text": "Airport Systems: Terminal 2 BHS throughput capacity is 4,500 bags per hour.",
                "embedding": mock_embedding_airport
            }],
            domain_id=3,  # Airport Systems domain
            document_type="technical_spec",
            project_name="Delhi Terminal 2",
            db_path=self.db_path
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    @patch("app.rag.retriever.generate_single_embedding")
    def test_domain_filtered_retrieval(self, mock_embed):
        """Verify retrieval filtered strictly by domain."""
        mock_embed.return_value = [0.15] * 768

        # 1. Search without domain filter -> both documents returned
        all_chunks = retrieve_relevant_chunks(
            query="policy and baggage",
            top_k=5,
            min_score=0.0,
            allowed_document_ids=[self.hr_doc_id, self.airport_doc_id],
            db_path=self.db_path
        )
        self.assertEqual(len(all_chunks), 2)

        # 2. Search filtered strictly by 'hr' domain
        hr_chunks = retrieve_relevant_chunks(
            query="policy and baggage",
            domain_slug="hr",
            top_k=5,
            min_score=0.0,
            allowed_document_ids=[self.hr_doc_id, self.airport_doc_id],
            db_path=self.db_path
        )
        self.assertEqual(len(hr_chunks), 1)
        self.assertEqual(hr_chunks[0]["document_id"], self.hr_doc_id)
        self.assertEqual(hr_chunks[0]["domain_slug"], "hr")

        # 3. Search filtered strictly by 'airport-systems' domain
        airport_chunks = retrieve_relevant_chunks(
            query="policy and baggage",
            domain_slug="airport-systems",
            top_k=5,
            min_score=0.0,
            allowed_document_ids=[self.hr_doc_id, self.airport_doc_id],
            db_path=self.db_path
        )
        self.assertEqual(len(airport_chunks), 1)
        self.assertEqual(airport_chunks[0]["document_id"], self.airport_doc_id)
        self.assertEqual(airport_chunks[0]["project_name"], "Delhi Terminal 2")

    @patch("app.rag.retriever.generate_single_embedding")
    def test_project_name_filtered_retrieval(self, mock_embed):
        """Verify retrieval filtered by project name."""
        mock_embed.return_value = [0.2] * 768

        results = retrieve_relevant_chunks(
            query="capacity",
            project_name="Delhi",
            top_k=5,
            min_score=0.0,
            allowed_document_ids=[self.hr_doc_id, self.airport_doc_id],
            db_path=self.db_path
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["document_id"], self.airport_doc_id)

    @patch("app.rag.retriever.generate_single_embedding")
    def test_insufficient_context_for_company_query(self, mock_embed):
        """Verify company question without matching chunks returns standardized insufficient context message."""
        mock_embed.return_value = [0.0] * 768

        # When min_score=0.9, mock embedding of 0.0 scores 0.0, so no chunks match
        res = answer_query(
            query="What is the CEO salary policy for 2026?",
            top_k=3,
            min_score=0.9,
            allowed_document_ids=[self.hr_doc_id],
            db_path=self.db_path
        )
        self.assertEqual(res["retrieval_status"], "insufficient_context")
        self.assertIn("do not contain enough information", res["answer"])
        self.assertEqual(len(res["sources"]), 0)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.rag.embedder import EXPECTED_EMBEDDING_DIM
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.vector_store import initialize_database, save_document


class TestRetriever(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_retriever.db"
        initialize_database(self.db_path)

        # Populate with 2 test documents
        vec_1 = [0.0] * EXPECTED_EMBEDDING_DIM
        vec_1[0] = 1.0

        vec_2 = [0.0] * EXPECTED_EMBEDDING_DIM
        vec_2[1] = 1.0

        save_document(
            filename="leave_policy.pdf",
            file_type=".pdf",
            content_hash="hash_leave",
            character_count=200,
            chunks=[{"chunk_index": 0, "text": "Annual leave policy: Employees get 20 days off.", "embedding": vec_1}],
            db_path=self.db_path
        )

        save_document(
            filename="travel_policy.pdf",
            file_type=".pdf",
            content_hash="hash_travel",
            character_count=200,
            chunks=[{"chunk_index": 0, "text": "Travel reimbursement policy: Keep all food receipts.", "embedding": vec_2}],
            db_path=self.db_path
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_empty_query_returns_empty_list(self):
        self.assertEqual(retrieve_relevant_chunks("", db_path=self.db_path), [])
        self.assertEqual(retrieve_relevant_chunks("   ", db_path=self.db_path), [])

    @patch("app.rag.retriever.generate_single_embedding")
    def test_semantic_ranking_and_traceability(self, mock_embed):
        # Query embedding with high alignment to leave policy (dim 0) and moderate alignment to travel (dim 1)
        query_vec = [0.0] * EXPECTED_EMBEDDING_DIM
        query_vec[0] = 0.9
        query_vec[1] = 0.3
        mock_embed.return_value = query_vec

        results = retrieve_relevant_chunks("How many days off do I get?", top_k=2, min_score=0.1, db_path=self.db_path)

        self.assertEqual(len(results), 2)
        top_match = results[0]
        self.assertEqual(top_match["filename"], "leave_policy.pdf")
        self.assertEqual(top_match["chunk_index"], 0)
        self.assertIn("Annual leave policy", top_match["text"])
        self.assertIn("similarity", top_match)
        self.assertIn("document_id", top_match)
        self.assertIn("chunk_id", top_match)
        self.assertGreater(results[0]["similarity"], results[1]["similarity"])

    @patch("app.rag.retriever.generate_single_embedding")
    def test_min_score_filters_unrelated_chunks(self, mock_embed):
        query_vec = [0.0] * EXPECTED_EMBEDDING_DIM
        query_vec[0] = 1.0  # matches leave_policy exactly (score 1.0), travel_policy is orthogonal (score 0.0)
        mock_embed.return_value = query_vec

        results = retrieve_relevant_chunks("Leave question", top_k=5, min_score=0.5, db_path=self.db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "leave_policy.pdf")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from app.rag.vector_store import (
    EXPECTED_EMBEDDING_DIM,
    calculate_cosine_similarity,
    delete_document,
    get_connection,
    get_database_stats,
    get_document,
    get_document_by_hash,
    get_document_chunks,
    initialize_database,
    list_documents,
    save_document,
    search_similar_chunks,
)


class TestVectorStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sankalit.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cosine_similarity_cases(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        v_zero = [0.0, 0.0, 0.0]

        # Identical
        self.assertAlmostEqual(calculate_cosine_similarity(v1, v2), 1.0, places=5)
        # Orthogonal
        self.assertAlmostEqual(calculate_cosine_similarity(v1, v3), 0.0, places=5)
        # Zero magnitude
        self.assertEqual(calculate_cosine_similarity(v1, v_zero), 0.0)

        # Mismatched length
        with self.assertRaises(ValueError):
            calculate_cosine_similarity([1.0, 2.0], [1.0])

        # Empty vector
        with self.assertRaises(ValueError):
            calculate_cosine_similarity([], [])

    def test_save_and_retrieve_document(self):
        dummy_embedding = [0.05] * EXPECTED_EMBEDDING_DIM
        chunks = [
            {"chunk_index": 0, "text": "Chunk zero content", "embedding": dummy_embedding},
            {"chunk_index": 1, "text": "Chunk one content", "embedding": dummy_embedding},
        ]

        doc_id = save_document(
            filename="test_notes.pdf",
            file_type=".pdf",
            content_hash="abc123hash",
            character_count=150,
            chunks=chunks,
            db_path=self.db_path
        )
        self.assertIsInstance(doc_id, int)
        self.assertGreater(doc_id, 0)

        # Retrieve by ID
        doc = get_document(doc_id, db_path=self.db_path)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["filename"], "test_notes.pdf")
        self.assertEqual(doc["content_hash"], "abc123hash")
        self.assertEqual(doc["chunk_count"], 2)

        # Retrieve by hash
        doc_by_hash = get_document_by_hash("abc123hash", db_path=self.db_path)
        self.assertIsNotNone(doc_by_hash)
        self.assertEqual(doc_by_hash["id"], doc_id)

        # Retrieve chunks
        stored_chunks = get_document_chunks(doc_id, db_path=self.db_path)
        self.assertEqual(len(stored_chunks), 2)
        self.assertEqual(stored_chunks[0]["chunk_index"], 0)
        self.assertEqual(stored_chunks[1]["chunk_index"], 1)

    def test_duplicate_prevention(self):
        dummy_embedding = [0.1] * EXPECTED_EMBEDDING_DIM
        chunks = [{"chunk_index": 0, "text": "Unique text", "embedding": dummy_embedding}]

        id_1 = save_document(
            filename="file1.docx",
            file_type=".docx",
            content_hash="same_hash",
            character_count=50,
            chunks=chunks,
            db_path=self.db_path
        )

        id_2 = save_document(
            filename="file2.docx",
            file_type=".docx",
            content_hash="same_hash",
            character_count=50,
            chunks=chunks,
            db_path=self.db_path
        )

        self.assertEqual(id_1, id_2)
        stats = get_database_stats(self.db_path)
        self.assertEqual(stats["documents"], 1)
        self.assertEqual(stats["chunks"], 1)

    def test_delete_cascades_chunks(self):
        dummy_embedding = [0.1] * EXPECTED_EMBEDDING_DIM
        chunks = [
            {"chunk_index": 0, "text": "Text 1", "embedding": dummy_embedding},
            {"chunk_index": 1, "text": "Text 2", "embedding": dummy_embedding},
        ]
        doc_id = save_document(
            filename="delete_me.pdf",
            file_type=".pdf",
            content_hash="del_hash",
            character_count=100,
            chunks=chunks,
            db_path=self.db_path
        )

        stats_before = get_database_stats(self.db_path)
        self.assertEqual(stats_before["documents"], 1)
        self.assertEqual(stats_before["chunks"], 2)

        # Delete document
        deleted = delete_document(doc_id, db_path=self.db_path)
        self.assertTrue(deleted)

        stats_after = get_database_stats(self.db_path)
        self.assertEqual(stats_after["documents"], 0)
        self.assertEqual(stats_after["chunks"], 0)

        # Deleting non-existent returns False
        self.assertFalse(delete_document(99999, db_path=self.db_path))

    def test_search_similar_chunks(self):
        # Create 2 documents with distinct embeddings
        vec_a = [0.0] * EXPECTED_EMBEDDING_DIM
        vec_a[0] = 1.0  # high along dim 0

        vec_b = [0.0] * EXPECTED_EMBEDDING_DIM
        vec_b[1] = 1.0  # high along dim 1

        chunks_a = [{"chunk_index": 0, "text": "Topic A content", "embedding": vec_a}]
        chunks_b = [{"chunk_index": 0, "text": "Topic B content", "embedding": vec_b}]

        save_document("doc_a.pdf", ".pdf", "hash_a", 100, chunks_a, db_path=self.db_path)
        save_document("doc_b.pdf", ".pdf", "hash_b", 100, chunks_b, db_path=self.db_path)

        # Search with vector close to vec_a
        query_vec = [0.0] * EXPECTED_EMBEDDING_DIM
        query_vec[0] = 0.9
        query_vec[1] = 0.1

        results = search_similar_chunks(query_vec, top_k=2, min_score=0.1, db_path=self.db_path)
        self.assertEqual(len(results), 2)
        # First result should be Topic A
        self.assertEqual(results[0]["filename"], "doc_a.pdf")
        self.assertGreater(results[0]["similarity"], results[1]["similarity"])

        # Test min_score filtering
        high_thresh_results = search_similar_chunks(query_vec, top_k=2, min_score=0.5, db_path=self.db_path)
        self.assertEqual(len(high_thresh_results), 1)
        self.assertEqual(high_thresh_results[0]["filename"], "doc_a.pdf")


if __name__ == "__main__":
    unittest.main()


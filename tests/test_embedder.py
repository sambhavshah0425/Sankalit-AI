import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.rag.embedder import (
    EXPECTED_EMBEDDING_DIM,
    DEFAULT_BATCH_SIZE,
    embed_chunks,
    generate_embeddings,
    generate_single_embedding,
)


class TestEmbedder(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(generate_embeddings([]), [])
        self.assertEqual(embed_chunks([]), [])

    def test_whitespace_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_embeddings(["   ", "valid text"])

        with self.assertRaises(ValueError):
            generate_single_embedding("   ")

    @patch("httpx.Client")
    def test_generate_embeddings_mocked_success(self, mock_client_cls):
        dummy_embedding = [0.1] * EXPECTED_EMBEDDING_DIM
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [dummy_embedding, dummy_embedding]
        }
        mock_client.post.return_value = mock_response

        texts = ["Text one", "Text two"]
        results = generate_embeddings(texts)

        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0]), EXPECTED_EMBEDDING_DIM)
        self.assertEqual(len(results[1]), EXPECTED_EMBEDDING_DIM)

    @patch("httpx.Client")
    def test_generate_embeddings_dimension_mismatch(self, mock_client_cls):
        # Return 512 dimensions instead of 768
        bad_embedding = [0.1] * 512
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [bad_embedding]
        }
        mock_client.post.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            generate_embeddings(["Text one"])
        self.assertIn("Embedding dimension mismatch", str(ctx.exception))

    @patch("httpx.Client")
    def test_embed_chunks_mocked(self, mock_client_cls):
        dummy_embedding = [0.05] * EXPECTED_EMBEDDING_DIM
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [dummy_embedding]
        }
        mock_client.post.return_value = mock_response

        chunks = [{"chunk_index": 0, "text": "Sample chunk", "character_count": 12}]
        embedded = embed_chunks(chunks)

        self.assertEqual(len(embedded), 1)
        self.assertEqual(embedded[0]["chunk_index"], 0)
        self.assertEqual(embedded[0]["embedding"], dummy_embedding)


class TestEmbedderIntegration(unittest.TestCase):
    """Real local integration test against Ollama nomic-embed-text if reachable."""
    def test_real_ollama_embedding(self):
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get("http://localhost:11434/api/tags")
                if resp.status_code != 200:
                    self.skipTest("Ollama is not reachable on localhost:11434")
        except Exception:
            self.skipTest("Ollama is not reachable on localhost:11434")

        emb = generate_single_embedding("Sankalit local intelligence test.")
        self.assertEqual(len(emb), EXPECTED_EMBEDDING_DIM)
        self.assertIsInstance(emb[0], float)


if __name__ == "__main__":
    unittest.main()


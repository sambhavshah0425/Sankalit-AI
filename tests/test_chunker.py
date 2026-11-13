import unittest

from app.rag.chunker import chunk_text


class TestChunker(unittest.TestCase):
    def test_empty_and_whitespace_text(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   \n\t  "), [])
        self.assertEqual(chunk_text(None), [])

    def test_chunk_generation_and_indexing(self):
        # 2500 character text
        words = ["Sankalit"] * 300
        text = " ".join(words)

        chunks = chunk_text(text, chunk_size=500, overlap=50, min_chunk_size=50)
        self.assertGreater(len(chunks), 1)

        # Check chunk indices are sequential
        for idx, chunk in enumerate(chunks):
            self.assertEqual(chunk["chunk_index"], idx)
            self.assertIn("text", chunk)
            self.assertEqual(chunk["character_count"], len(chunk["text"]))
            self.assertLessEqual(chunk["character_count"], 550)

    def test_chunk_overlap(self):
        text = "The quick brown fox jumps over the lazy dog. " * 20
        chunk_size = 200
        overlap = 50
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap, min_chunk_size=30)

        self.assertGreater(len(chunks), 1)
        # Check that consecutive chunks share content due to overlap
        first_chunk_end = chunks[0]["text"][-30:]
        second_chunk_start = chunks[1]["text"][:60]
        # At least some words in first_chunk_end should appear in second_chunk_start
        common_words = set(first_chunk_end.split()) & set(second_chunk_start.split())
        self.assertTrue(len(common_words) > 0)

    def test_invalid_parameters(self):
        text = "Valid text for testing errors."

        with self.assertRaises(ValueError):
            chunk_text(text, chunk_size=0)

        with self.assertRaises(ValueError):
            chunk_text(text, chunk_size=-10)

        with self.assertRaises(ValueError):
            chunk_text(text, chunk_size=200, overlap=200)

        with self.assertRaises(ValueError):
            chunk_text(text, chunk_size=200, overlap=250)

        with self.assertRaises(ValueError):
            chunk_text(text, chunk_size=200, min_chunk_size=300)


if __name__ == "__main__":
    unittest.main()


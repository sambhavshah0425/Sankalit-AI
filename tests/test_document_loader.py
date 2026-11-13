import os
import tempfile
import unittest
from pathlib import Path

from app.rag.document_loader import load_document, extract_pdf, extract_docx
from tests.helpers import create_sample_docx, create_sample_pdf


class TestDocumentLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_docx_success(self):
        sample_text = "Sankalit Consultant provides enterprise AI advisory services.\n\nAll systems run strictly locally."
        file_path = create_sample_docx(sample_text, "test.docx", self.dir_path)

        result = load_document(str(file_path))
        self.assertEqual(result["filename"], "test.docx")
        self.assertEqual(result["file_type"], ".docx")
        self.assertIn("Sankalit Consultant provides enterprise AI advisory services.", result["text"])
        self.assertIn("All systems run strictly locally.", result["text"])
        self.assertGreater(result["character_count"], 50)

    def test_extract_pdf_success(self):
        sample_text = "Sankalit New Joiner Guide and Policy Notes."
        file_path = create_sample_pdf(sample_text, "test.pdf", self.dir_path)

        result = load_document(str(file_path))
        self.assertEqual(result["filename"], "test.pdf")
        self.assertEqual(result["file_type"], ".pdf")
        self.assertIn("Sankalit New Joiner Guide", result["text"])
        self.assertIn("[Page 1]", result["text"])
        self.assertGreater(result["character_count"], 10)

    def test_unsupported_file_extension(self):
        bad_file = self.dir_path / "data.txt"
        bad_file.write_text("plain text", encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            load_document(str(bad_file))
        self.assertIn("Unsupported file format", str(ctx.exception))

    def test_nonexistent_file(self):
        missing_file = self.dir_path / "does_not_exist.pdf"
        with self.assertRaises(FileNotFoundError):
            load_document(str(missing_file))

    def test_empty_docx_raises_value_error(self):
        empty_docx = create_sample_docx("", "empty.docx", self.dir_path)
        with self.assertRaises(ValueError) as ctx:
            load_document(str(empty_docx))
        self.assertIn("No readable text found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


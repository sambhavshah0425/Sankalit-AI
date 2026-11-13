"""
Shared test helper utilities for generating synthetic PDF and DOCX files.
"""

import tempfile
from pathlib import Path
import docx


def create_sample_docx(text: str, filename: str = "sample.docx", target_dir: Path = None) -> Path:
    """Create a temporary valid DOCX file with given text."""
    dir_path = target_dir or Path(tempfile.gettempdir())
    file_path = dir_path / filename
    doc = docx.Document()
    for paragraph in text.split("\n\n"):
        if paragraph.strip():
            doc.add_paragraph(paragraph.strip())
    doc.save(str(file_path))
    return file_path


def create_sample_pdf(text: str, filename: str = "sample.pdf", target_dir: Path = None) -> Path:
    """Create a temporary valid PDF file with extractable text."""
    dir_path = target_dir or Path(tempfile.gettempdir())
    file_path = dir_path / filename

    clean_text = "".join(ch if (ch.isalnum() or ch in " .,;:!-?()") else " " for ch in text)
    escaped_text = clean_text.replace("(", "\\(").replace(")", "\\)")
    text_bytes = f"BT\n/F1 12 Tf\n72 712 Td\n({escaped_text}) Tj\nET\n".encode("latin-1", errors="replace")
    stream_length = len(text_bytes)

    parts = [
        b"%PDF-1.4\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {stream_length} >>\nstream\n".encode("latin-1"),
        text_bytes,
        b"endstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"xref\n0 6\n0000000000 65535 f \n",
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n",
        b"startxref\n500\n%%EOF\n",
    ]
    pdf_content = b"".join(parts)

    with open(file_path, "wb") as f:
        f.write(pdf_content)

    return file_path

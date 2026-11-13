from pathlib import Path
from pypdf import PdfReader
from docx import Document


SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def extract_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(file_path)

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            pages.append(
                f"[Page {page_number}]\n{text.strip()}"
            )

    return "\n\n".join(pages)


def extract_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    document = Document(file_path)

    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    return "\n\n".join(paragraphs)


def load_document(file_path: str) -> dict:
    """
    Load a PDF or DOCX document and return extracted text.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Unsupported file format. Only PDF and DOCX are supported."
        )

    try:
        if path.suffix.lower() == ".pdf":
            extracted_text = extract_pdf(str(path))

        else:
            extracted_text = extract_docx(str(path))

        if not extracted_text.strip():
            raise ValueError(
                "No readable text found in the document. "
                "The PDF may contain scanned images."
            )

        return {
            "filename": path.name,
            "file_type": path.suffix.lower(),
            "text": extracted_text,
            "character_count": len(extracted_text)
        }

    except Exception as exc:
        raise ValueError(
            f"Failed to process {path.name}: {str(exc)}"
        ) from exc
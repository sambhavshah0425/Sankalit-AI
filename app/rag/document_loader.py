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
    """Extract text from a DOCX file including paragraphs and tables in document order."""
    document = Document(file_path)
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    content_blocks = []

    for element in document.element.body:
        if element.tag.endswith('p'):
            p = Paragraph(element, document)
            text = p.text.strip()
            if text:
                content_blocks.append(text)
        elif element.tag.endswith('tbl'):
            tbl = Table(element, document)
            table_rows = []
            for row in tbl.rows:
                seen_cells = set()
                row_cells = []
                for cell in row.cells:
                    if cell._tc not in seen_cells:
                        seen_cells.add(cell._tc)
                        txt = cell.text.strip().replace("\n", " ")
                        if txt:
                            row_cells.append(txt)
                if row_cells:
                    table_rows.append(" | ".join(row_cells))
            if table_rows:
                content_blocks.append("\n".join(table_rows))

    return "\n\n".join(content_blocks)


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
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.document_loader import load_document, SUPPORTED_EXTENSIONS
from app.rag.chunker import chunk_text
from app.rag.embedder import embed_chunks, EXPECTED_EMBEDDING_DIM
from app.rag.vector_store import (
    get_document_by_hash,
    save_document,
)
from app.services.classification_service import classify_document_content

logger = logging.getLogger(__name__)


def calculate_content_hash(text: str) -> str:
    """Calculate SHA-256 hash of extracted text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest_document(
    file_path: str,
    db_path: Optional[Path] = None,
    chunk_size: int = 1000,
    overlap: int = 150,
    batch_size: int = 16,
    owner_id: Optional[int] = None,
    visibility: str = "COMPANY",
    access_policy: Optional[str] = None,
    department_ids: Optional[List[int]] = None,
    document_title: Optional[str] = None,
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    project_name: Optional[str] = None,
    project_identifier: Optional[str] = None,
    document_type: Optional[str] = None,
    document_date: Optional[str] = None,
    document_version: str = "1.0",
    confidentiality_level: str = "INTERNAL"
) -> Dict[str, Any]:
    """
    Ingest a PDF or DOCX document with security and knowledge taxonomy metadata:
    1. Validate file existence and extension.
    2. Extract text using load_document.
    3. Calculate SHA-256 hash.
    4. Check for duplicate content in SQLite.
    5. If duplicate, skip embedding generation and return existing metadata.
    6. Run intelligent document classification if taxonomy is unassigned.
    7. Chunk text and generate local embeddings in small batches.
    8. Save document, security metadata, taxonomy, and chunks transactionally.
    9. Return structured ingestion report.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format '{path.suffix}'. Only PDF and DOCX are supported."
        )

    # 1. Extract document text
    loaded = load_document(str(path))
    extracted_text = loaded["text"]
    filename = loaded["filename"]
    file_type = loaded["file_type"]
    character_count = loaded["character_count"]

    # 2. Calculate content hash
    content_hash = calculate_content_hash(extracted_text)

    # 3. Check for existing document by hash
    existing_doc = get_document_by_hash(content_hash, db_path=db_path)
    if existing_doc:
        logger.info(
            f"Document with identical content already indexed (ID: {existing_doc['id']}). Skipping embedding."
        )
        return {
            "document_id": existing_doc["id"],
            "filename": existing_doc["filename"],
            "document_title": existing_doc.get("document_title", filename),
            "file_type": existing_doc["file_type"],
            "content_hash": content_hash,
            "character_count": existing_doc["character_count"],
            "total_chunks": existing_doc.get("chunk_count", 0),
            "embedded_chunks": 0,
            "ingestion_status": "duplicate_skipped",
            "duplicate_status": True,
            "visibility": existing_doc.get("visibility", "COMPANY"),
            "owner_id": existing_doc.get("owner_id"),
            "domain_id": existing_doc.get("domain_id"),
            "category_id": existing_doc.get("category_id")
        }

    # 4. Intelligent Classification
    effective_domain_id = domain_id
    effective_category_id = category_id
    effective_type = document_type or "general"
    effective_project = project_name
    classification_status = "UNCLASSIFIED"
    classification_confidence = 0.0
    classification_explanation = None
    final_dept_ids = list(department_ids) if department_ids else []

    if effective_domain_id is None:
        classification = classify_document_content(extracted_text, filename, db_path=db_path)
        effective_domain_id = classification.get("domain_id")
        effective_category_id = classification.get("category_id")
        if not document_type:
            effective_type = classification.get("document_type", "general")
        if not project_name and classification.get("project_name"):
            effective_project = classification.get("project_name")
        classification_status = classification.get("status", "UNCLASSIFIED")
        classification_confidence = classification.get("confidence", 0.0)
        classification_explanation = classification.get("explanation")

        suggested_dept_id = classification.get("department_id")
        if suggested_dept_id and not final_dept_ids:
            final_dept_ids = [suggested_dept_id]
    else:
        classification_status = "CLASSIFIED"
        classification_confidence = 1.0
        classification_explanation = "Manually assigned at ingestion"

    # 5. Chunk text
    chunks = chunk_text(
        text=extracted_text,
        chunk_size=chunk_size,
        overlap=overlap
    )

    if not chunks:
        raise ValueError("Document yielded no chunks after processing.")

    # 6. Generate embeddings in hardware-conscious batches
    embedded_chunks = embed_chunks(chunks, batch_size=batch_size)

    # 7. Validate embedding dimensions
    for chunk in embedded_chunks:
        emb = chunk.get("embedding")
        if not emb or len(emb) != EXPECTED_EMBEDDING_DIM:
            raise ValueError(
                f"Embedding validation failed: chunk {chunk.get('chunk_index')} "
                f"has dimension {len(emb) if emb else 0}, expected {EXPECTED_EMBEDDING_DIM}."
            )

    # 8. Transactional save to vector store with security & taxonomy metadata
    document_id = save_document(
        filename=filename,
        file_type=file_type,
        content_hash=content_hash,
        character_count=character_count,
        chunks=embedded_chunks,
        owner_id=owner_id,
        visibility=visibility,
        access_policy=access_policy,
        department_ids=final_dept_ids,
        document_title=document_title or filename,
        domain_id=effective_domain_id,
        category_id=effective_category_id,
        project_name=effective_project,
        project_identifier=project_identifier,
        document_type=effective_type,
        document_date=document_date,
        document_version=document_version,
        confidentiality_level=confidentiality_level,
        classification_status=classification_status,
        classification_confidence=classification_confidence,
        classification_explanation=classification_explanation,
        db_path=db_path
    )

    return {
        "document_id": document_id,
        "filename": filename,
        "document_title": document_title or filename,
        "file_type": file_type,
        "content_hash": content_hash,
        "character_count": character_count,
        "total_chunks": len(chunks),
        "embedded_chunks": len(embedded_chunks),
        "ingestion_status": "success",
        "duplicate_status": False,
        "visibility": visibility,
        "owner_id": owner_id,
        "department_ids": final_dept_ids,
        "domain_id": effective_domain_id,
        "category_id": effective_category_id,
        "document_type": effective_type,
        "project_name": effective_project,
        "document_version": document_version,
        "classification_status": classification_status,
        "classification_confidence": classification_confidence
    }

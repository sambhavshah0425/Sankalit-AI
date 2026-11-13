"""Semantic retrieval engine with security authorization and domain-aware filtering.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.embedder import generate_single_embedding
from app.rag.vector_store import get_db, search_similar_chunks

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
DEFAULT_MIN_SIMILARITY = 0.25


def retrieve_relevant_chunks(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SIMILARITY,
    allowed_document_ids: Optional[List[int]] = None,
    domain_id: Optional[int] = None,
    domain_slug: Optional[str] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    project_name: Optional[str] = None,
    document_type: Optional[str] = None,
    filename: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Perform semantic retrieval against indexed document chunks:
    1. Validate query input.
    2. Check authorized document boundaries (short-circuits if 0 permitted documents).
    3. Resolve domain_id from domain_slug if provided.
    4. Generate query embedding via nomic-embed-text.
    5. Calculate cosine similarity against stored chunks of AUTHORIZED documents only.
    6. Filter by minimum similarity threshold and metadata criteria.
    7. Rank and return top-k most relevant chunks with rich metadata.
    """
    if not query or not query.strip():
        logger.warning("Empty query received in retriever.")
        return []

    # If security check resolved 0 authorized documents, return [] immediately
    if allowed_document_ids is not None and len(allowed_document_ids) == 0:
        logger.info("User has no authorized documents; returning empty chunk list.")
        return []

    clean_query = query.strip()

    # Resolve domain_slug to domain_id if needed
    effective_domain_id = domain_id
    if effective_domain_id is None and domain_slug:
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT id FROM knowledge_domains WHERE slug = ?",
                (domain_slug.strip().lower(),)
            ).fetchone()
            if row:
                effective_domain_id = row["id"]

    # Generate embedding for the query
    query_embedding = generate_single_embedding(clean_query)

    # Search vector store filtering by authorized document IDs and metadata
    results = search_similar_chunks(
        query_embedding=query_embedding,
        top_k=top_k,
        min_score=min_score,
        allowed_document_ids=allowed_document_ids,
        domain_id=effective_domain_id,
        category_id=category_id,
        department_id=department_id,
        project_name=project_name,
        document_type=document_type,
        filename=filename,
        db_path=db_path
    )

    return results

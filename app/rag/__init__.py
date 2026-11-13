"""
Sankalit Intelligence RAG Module.
Provides local document ingestion, chunking, embedding, vector storage, retrieval, and generation.
"""

from app.rag.document_loader import load_document, SUPPORTED_EXTENSIONS
from app.rag.chunker import chunk_text
from app.rag.embedder import (
    generate_embeddings,
    generate_single_embedding,
    embed_chunks,
    EMBEDDING_MODEL,
    EXPECTED_EMBEDDING_DIM,
)
from app.rag.vector_store import (
    initialize_database,
    get_connection,
    save_document,
    get_document,
    get_document_by_hash,
    list_documents,
    delete_document,
    search_similar_chunks,
    get_database_stats,
    calculate_cosine_similarity,
)
from app.rag.ingestion import ingest_document
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.rag_pipeline import answer_query, answer_query_async

__all__ = [
    "load_document",
    "SUPPORTED_EXTENSIONS",
    "chunk_text",
    "generate_embeddings",
    "generate_single_embedding",
    "embed_chunks",
    "EMBEDDING_MODEL",
    "EXPECTED_EMBEDDING_DIM",
    "initialize_database",
    "get_connection",
    "save_document",
    "get_document",
    "get_document_by_hash",
    "list_documents",
    "delete_document",
    "search_similar_chunks",
    "get_database_stats",
    "calculate_cosine_similarity",
    "ingest_document",
    "retrieve_relevant_chunks",
    "answer_query",
    "answer_query_async",
]


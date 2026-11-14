"""Production-conscious local RAG pipeline with Company-First AI identity,
domain-aware retrieval, structured context isolation, and citation validation.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from dotenv import load_dotenv

from app.ai.citation_validator import validate_citations
from app.ai.context_builder import build_rag_context
from app.ai.query_classifier import (
    CLASS_GENERAL_KNOWLEDGE,
    CLASS_GENERAL_PROFESSIONAL,
    classify_query,
)
from app.ai.query_normalizer import normalize_query
from app.ai.system_prompt import build_system_prompt
from app.rag.retriever import retrieve_relevant_chunks

load_dotenv()

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The available documents do not contain enough information in the Sankalit company knowledge base to answer this question accurately."
)


def clean_plain_text(text: str) -> str:
    """Clean markdown asterisks, bold/italics, quotes, and header symbols to produce pure plain text."""
    if not text:
        return ""
    # Strip markdown bold/italics asterisks: **text** -> text, *text* -> text
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
    clean = re.sub(r"__([^_]+)__", r"\1", clean)
    clean = re.sub(r"_([^_]+)_", r"\1", clean)
    # Strip any remaining asterisks (e.g. '* \n' or leftover '**' or bullet points)
    clean = clean.replace("*", "")
    # Strip leading markdown headers (#, ##, etc.)
    clean = re.sub(r"^#{1,6}\s*", "", clean, flags=re.MULTILINE)
    # Remove escaped quotes and quotation marks around words/phrases
    clean = clean.replace(r'\"', '').replace(r"\'", "'")
    clean = clean.replace('"', '')
    # Clean leading bullet symbols like '- ' or '• '
    clean = re.sub(r"^\s*[-•]\s*", "", clean, flags=re.MULTILINE)
    # Normalize excessive newlines
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def build_context_string(chunks: List[Dict[str, Any]]) -> str:
    """Format chunks into context string (backwards compatibility wrapper)."""
    ctx, _ = build_rag_context(chunks)
    return ctx


def build_rag_prompt(query: str, context_str: str, system_prompt: Optional[str] = None) -> str:
    """Construct full prompt separating system instructions from untrusted context."""
    if system_prompt is None:
        system_prompt = build_system_prompt()
    return f"""### SYSTEM INSTRUCTIONS:
{system_prompt}

### RETRIEVED CONTEXT:
<context>
{context_str}
</context>

### USER QUESTION:
{query}

### RESPONSE:"""


def answer_query(
    query: str,
    top_k: int = 4,
    min_score: float = 0.25,
    allowed_document_ids: Optional[List[int]] = None,
    domain_id: Optional[int] = None,
    domain_slug: Optional[str] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    project_name: Optional[str] = None,
    document_type: Optional[str] = None,
    db_path: Optional[Path] = None,
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Synchronous end-to-end RAG pipeline with company intelligence and document security:
    1. Query understanding and normalization.
    2. Semantic retrieval restricted to authorized documents and domains.
    3. Context construction with untrusted evidence isolation boundaries.
    4. Local LLM inference via Ollama qwen3:1.7b.
    5. Citation validation against retrieved chunks.
    """
    if not query or not query.strip():
        return {
            "answer": "Query cannot be empty.",
            "sources": [],
            "retrieved_chunks": [],
            "model": OLLAMA_MODEL,
            "retrieval_status": "empty_query"
        }

    clean_query = query.strip()

    # Step 1: Query Understanding & Normalization
    classification = classify_query(clean_query)
    norm_info = normalize_query(clean_query)
    effective_domain_slug = domain_slug or classification.get("domain_slug")

    # Step 2: Semantic retrieval restricted to authorized documents
    retrieved_chunks = retrieve_relevant_chunks(
        query=norm_info["rewritten_query"],
        top_k=top_k,
        min_score=min_score,
        allowed_document_ids=allowed_document_ids,
        domain_id=domain_id,
        domain_slug=effective_domain_slug,
        category_id=category_id,
        department_id=department_id,
        project_name=project_name,
        document_type=document_type,
        db_path=db_path
    )

    # If domain filter yielded 0 chunks, try general search across all authorized docs
    if not retrieved_chunks and effective_domain_slug and domain_id is None:
        retrieved_chunks = retrieve_relevant_chunks(
            query=clean_query,
            top_k=top_k,
            min_score=min_score,
            allowed_document_ids=allowed_document_ids,
            category_id=category_id,
            department_id=department_id,
            project_name=project_name,
            document_type=document_type,
            db_path=db_path
        )

    # Step 3: Insufficient Context & General Question Handling
    if not retrieved_chunks:
        is_general = classification["classification"] in (CLASS_GENERAL_KNOWLEDGE, CLASS_GENERAL_PROFESSIONAL)
        if is_general:
            # Answer general professional question with explicit disclaimer
            try:
                system_prompt = build_system_prompt(db_path=db_path)
                gen_prompt = (
                    f"{system_prompt}\n\n"
                    f"USER QUESTION: {clean_query}\n\n"
                    f"INSTRUCTIONS: The user is asking a general technical/professional question. "
                    f"Answer concisely based on standard industry principles. "
                    f"Note clearly that this is general professional knowledge and not an internal company policy of Sankalit Consultant."
                )
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": OLLAMA_MODEL,
                            "prompt": gen_prompt,
                            "stream": False,
                            "think": False,
                            "options": {
                                "num_ctx": 2048,
                                "num_predict": 384,
                                "temperature": 0.2
                            }
                        }
                    )
                    resp.raise_for_status()
                    answer_text = resp.json().get("response", "").strip()
                return {
                    "answer": answer_text,
                    "query": clean_query,
                    "sources": [],
                    "retrieved_chunks": [],
                    "classification": classification["classification"],
                    "model": OLLAMA_MODEL,
                    "retrieval_status": "general_knowledge"
                }
            except Exception:
                pass

        return {
            "answer": INSUFFICIENT_CONTEXT_MESSAGE,
            "query": clean_query,
            "sources": [],
            "retrieved_chunks": [],
            "classification": classification["classification"],
            "model": OLLAMA_MODEL,
            "retrieval_status": "insufficient_context"
        }

    # Step 4: Context Construction
    context_str, included_chunks = build_rag_context(retrieved_chunks)
    system_prompt = build_system_prompt(db_path=db_path)
    prompt = build_rag_prompt(clean_query, context_str, system_prompt)

    sources = [
        {
            "filename": c.get("filename"),
            "chunk_index": c.get("chunk_index"),
            "similarity": c.get("similarity"),
            "document_title": c.get("document_title"),
            "domain_slug": c.get("domain_slug")
        }
        for c in included_chunks
    ]

    # Step 5: Local LLM Inference
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": 2048,
                        "num_predict": 384,
                        "temperature": 0.1
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            answer_text = result.get("response", "").strip()
            answer_text = clean_plain_text(answer_text)

        # Step 6: Citation Validation
        citation_analysis = validate_citations(answer_text, included_chunks)

        return {
            "answer": answer_text or INSUFFICIENT_CONTEXT_MESSAGE,
            "query": clean_query,
            "normalized_query": norm_info["normalized_query"],
            "classification": classification["classification"],
            "detected_domain": classification["domain_slug"],
            "sources": sources,
            "citations": citation_analysis["validated_citations"],
            "unverified_citations": citation_analysis["unverified_citations"],
            "has_valid_citations": citation_analysis["has_valid_citations"],
            "retrieved_chunks": included_chunks,
            "model": OLLAMA_MODEL,
            "retrieval_status": "success"
        }

    except Exception as exc:
        logger.error(f"RAG generation failed: {exc}")
        raise RuntimeError(f"RAG inference error: {exc}") from exc


async def answer_query_async(
    query: str,
    top_k: int = 4,
    min_score: float = 0.25,
    allowed_document_ids: Optional[List[int]] = None,
    domain_id: Optional[int] = None,
    domain_slug: Optional[str] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    project_name: Optional[str] = None,
    document_type: Optional[str] = None,
    db_path: Optional[Path] = None,
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Asynchronous end-to-end RAG pipeline for FastAPI endpoints.
    """
    if not query or not query.strip():
        return {
            "answer": "Query cannot be empty.",
            "sources": [],
            "retrieved_chunks": [],
            "model": OLLAMA_MODEL,
            "retrieval_status": "empty_query"
        }

    clean_query = query.strip()

    # Step 1: Query Understanding & Normalization
    classification = classify_query(clean_query)
    norm_info = normalize_query(clean_query)
    effective_domain_slug = domain_slug or classification.get("domain_slug")

    # Step 2: Semantic retrieval restricted to authorized documents
    retrieved_chunks = retrieve_relevant_chunks(
        query=norm_info["rewritten_query"],
        top_k=top_k,
        min_score=min_score,
        allowed_document_ids=allowed_document_ids,
        domain_id=domain_id,
        domain_slug=effective_domain_slug,
        category_id=category_id,
        department_id=department_id,
        project_name=project_name,
        document_type=document_type,
        db_path=db_path
    )

    # If domain filter yielded 0 chunks, try general search across all authorized docs
    if not retrieved_chunks and effective_domain_slug and domain_id is None:
        retrieved_chunks = retrieve_relevant_chunks(
            query=clean_query,
            top_k=top_k,
            min_score=min_score,
            allowed_document_ids=allowed_document_ids,
            category_id=category_id,
            department_id=department_id,
            project_name=project_name,
            document_type=document_type,
            db_path=db_path
        )

    # Step 3: Insufficient Context & General Question Handling
    if not retrieved_chunks:
        is_general = classification["classification"] in (CLASS_GENERAL_KNOWLEDGE, CLASS_GENERAL_PROFESSIONAL)
        if is_general:
            try:
                system_prompt = build_system_prompt(db_path=db_path)
                gen_prompt = (
                    f"{system_prompt}\n\n"
                    f"USER QUESTION: {clean_query}\n\n"
                    f"INSTRUCTIONS: The user is asking a general technical/professional question. "
                    f"Answer concisely based on standard industry principles. "
                    f"Note clearly that this is general professional knowledge and not an internal company policy of Sankalit Consultant."
                )
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": OLLAMA_MODEL,
                            "prompt": gen_prompt,
                            "stream": False,
                            "think": False,
                            "options": {
                                "num_ctx": 2048,
                                "num_predict": 384,
                                "temperature": 0.2
                            }
                        }
                    )
                    resp.raise_for_status()
                    answer_text = resp.json().get("response", "").strip()
                return {
                    "answer": answer_text,
                    "query": clean_query,
                    "sources": [],
                    "retrieved_chunks": [],
                    "classification": classification["classification"],
                    "model": OLLAMA_MODEL,
                    "retrieval_status": "general_knowledge"
                }
            except Exception:
                pass

        return {
            "answer": INSUFFICIENT_CONTEXT_MESSAGE,
            "query": clean_query,
            "sources": [],
            "retrieved_chunks": [],
            "classification": classification["classification"],
            "model": OLLAMA_MODEL,
            "retrieval_status": "insufficient_context"
        }

    # Step 4: Context Construction
    context_str, included_chunks = build_rag_context(retrieved_chunks)
    system_prompt = build_system_prompt(db_path=db_path)
    prompt = build_rag_prompt(clean_query, context_str, system_prompt)

    sources = [
        {
            "filename": c.get("filename"),
            "chunk_index": c.get("chunk_index"),
            "similarity": c.get("similarity"),
            "document_title": c.get("document_title"),
            "domain_slug": c.get("domain_slug")
        }
        for c in included_chunks
    ]

    # Step 5: Local LLM Inference via async httpx
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": 2048,
                        "num_predict": 384,
                        "temperature": 0.1
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            answer_text = result.get("response", "").strip()
            answer_text = clean_plain_text(answer_text)

        # Step 6: Citation Validation
        citation_analysis = validate_citations(answer_text, included_chunks)

        return {
            "answer": answer_text or INSUFFICIENT_CONTEXT_MESSAGE,
            "query": clean_query,
            "normalized_query": norm_info["normalized_query"],
            "classification": classification["classification"],
            "detected_domain": classification["domain_slug"],
            "sources": sources,
            "citations": citation_analysis["validated_citations"],
            "unverified_citations": citation_analysis["unverified_citations"],
            "has_valid_citations": citation_analysis["has_valid_citations"],
            "retrieved_chunks": included_chunks,
            "model": OLLAMA_MODEL,
            "retrieval_status": "success"
        }

    except Exception as exc:
        logger.error(f"RAG async generation failed: {exc}")
        raise RuntimeError(f"RAG inference error: {exc}") from exc

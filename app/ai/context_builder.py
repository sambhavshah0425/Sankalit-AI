"""Secure, budgeted context builder for local LLM inference.
Enforces untrusted boundary containers, deduplication, and memory/context budgeting.
"""

from typing import Any, Dict, List, Tuple
from app.ai.response_policy import UNTRUSTED_CONTENT_DISCLAIMER

# Conservative character budget for local Qwen3:1.7b running with num_ctx: 2048 on CPU
MAX_CONTEXT_CHARACTERS = 4800


def build_rag_context(
    retrieved_chunks: List[Dict[str, Any]],
    max_characters: int = MAX_CONTEXT_CHARACTERS
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Format retrieved chunks into a secure, structured context block:
    1. Deduplicates chunks with identical texts.
    2. Encapsulates chunks in XML-style untrusted evidence containers.
    3. Respects character/token budget to avoid CPU memory saturation.
    4. Includes the prompt-injection security disclaimer.
    Returns (context_string, list_of_included_chunks).
    """
    if not retrieved_chunks:
        return "", []

    seen_texts = set()
    unique_chunks: List[Dict[str, Any]] = []

    for chunk in retrieved_chunks:
        text_norm = " ".join(chunk.get("text", "").strip().split())
        if not text_norm or text_norm in seen_texts:
            continue
        seen_texts.add(text_norm)
        unique_chunks.append(chunk)

    context_parts: List[str] = [UNTRUSTED_CONTENT_DISCLAIMER, "\n### RETRIEVED COMPANY KNOWLEDGE BASE EVIDENCE:"]
    current_length = sum(len(p) for p in context_parts)
    included_chunks: List[Dict[str, Any]] = []

    for idx, c in enumerate(unique_chunks):
        doc_id = c.get("document_id", "unknown")
        filename = c.get("filename", "unknown")
        chunk_idx = c.get("chunk_index", 0)
        domain = c.get("domain_slug") or c.get("domain") or "general"
        similarity = c.get("similarity", 0.0)
        text = c.get("text", "").strip()

        chunk_block = (
            f'\n<evidence index="{idx}" doc_id="{doc_id}" filename="{filename}" '
            f'chunk_index="{chunk_idx}" domain="{domain}" similarity="{similarity:.4f}">\n'
            f"[Source: {filename}, Chunk {chunk_idx}]\n"
            f"{text}\n"
            f"</evidence>\n"
        )

        if current_length + len(chunk_block) > max_characters and included_chunks:
            # Exceeded budget, stop adding more chunks
            break

        context_parts.append(chunk_block)
        current_length += len(chunk_block)
        included_chunks.append(c)

    full_context_str = "\n".join(context_parts)
    return full_context_str, included_chunks

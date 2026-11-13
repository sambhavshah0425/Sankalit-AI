import os
from typing import Any, Dict, List
from dotenv import load_dotenv
import httpx

load_dotenv()

OLLAMA_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434"
)

EMBEDDING_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EXPECTED_EMBEDDING_DIM = 768
DEFAULT_BATCH_SIZE = 16


def generate_embeddings(
    texts: List[str],
    batch_size: int = DEFAULT_BATCH_SIZE
) -> List[List[float]]:
    """
    Generate local embeddings for multiple text inputs using Ollama.
    Processes in small batches to respect memory constraints on 8GB CPU hardware.
    """
    if not texts:
        return []

    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Embedding input cannot contain empty text.")

    all_embeddings: List[List[float]] = []

    try:
        with httpx.Client(timeout=300) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = client.post(
                    f"{OLLAMA_URL}/api/embed",
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": batch
                    }
                )
                response.raise_for_status()
                result = response.json()

                batch_embeddings = result.get("embeddings", [])
                if len(batch_embeddings) != len(batch):
                    raise ValueError(
                        f"Ollama returned {len(batch_embeddings)} embeddings for batch of {len(batch)}."
                    )

                for emb in batch_embeddings:
                    if len(emb) != EXPECTED_EMBEDDING_DIM:
                        raise ValueError(
                            f"Embedding dimension mismatch: expected {EXPECTED_EMBEDDING_DIM}, got {len(emb)}."
                        )
                    all_embeddings.append(emb)

        if not all_embeddings:
            raise ValueError("Ollama returned no embeddings.")

        return all_embeddings

    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Ollama embedding request failed: {exc}"
        ) from exc


def generate_single_embedding(text: str) -> List[float]:
    """Generate an embedding for a single query or text string."""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")
    embeddings = generate_embeddings([text])
    return embeddings[0]


def embed_chunks(
    chunks: List[Dict[str, Any]],
    batch_size: int = DEFAULT_BATCH_SIZE
) -> List[Dict[str, Any]]:
    """
    Generate embeddings and attach them to their chunks.
    """
    if not chunks:
        return []

    texts = [chunk["text"] for chunk in chunks]
    embeddings = generate_embeddings(texts, batch_size=batch_size)

    embedded_chunks = []
    for chunk, embedding in zip(chunks, embeddings):
        embedded_chunks.append({
            **chunk,
            "embedding": embedding
        })

    return embedded_chunks

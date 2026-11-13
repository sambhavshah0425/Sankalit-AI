
from typing import List, Dict


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 150,
    min_chunk_size: int = 100
) -> List[Dict]:

    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("Overlap must be smaller than chunk size.")

    if min_chunk_size < 0 or min_chunk_size > chunk_size:
        raise ValueError("Invalid minimum chunk size.")

    text = text.strip()
    chunks = []

    start = 0
    chunk_index = 0

    while start < len(text):

        end = min(start + chunk_size, len(text))

        # Move the ending boundary to a word boundary.
        if end < len(text):
            boundary = text.rfind(" ", start, end)

            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()

        if chunk and (
            len(chunk) >= min_chunk_size or not chunks
        ):
            chunks.append({
                "chunk_index": chunk_index,
                "text": chunk,
                "character_count": len(chunk)
            })

            chunk_index += 1

        if end >= len(text):
            break

        # Calculate the next starting position.
        next_start = max(start + 1, end - overlap)

        # Move forward to the next word boundary.
        while (
            next_start < end
            and not text[next_start - 1].isspace()
        ):
            next_start += 1

        start = next_start

    return chunks

"""Citation extraction and ground-truth validation against retrieved chunks.
"""

import re
from typing import Any, Dict, List, Set, Tuple

CITATION_REGEX = re.compile(
    r"\[Source:\s*([^,\]]+?)(?:,\s*Chunk\s*(\d+))?\]",
    re.IGNORECASE
)


def validate_citations(
    answer_text: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validate all citations in the LLM response against the retrieved source chunks.
    Ensures that every cited document and chunk was actually present in the evidence set.
    Returns:
    {
        "validated_citations": List[Dict],
        "unverified_citations": List[Dict],
        "has_valid_citations": bool,
        "citation_count": int,
        "valid_count": int
    }
    """
    if not answer_text or not retrieved_chunks:
        return {
            "validated_citations": [],
            "unverified_citations": [],
            "has_valid_citations": False,
            "citation_count": 0,
            "valid_count": 0
        }

    # Build lookup set of valid (filename, chunk_index) and valid filenames
    valid_pairs: Set[Tuple[str, int]] = set()
    valid_files: Set[str] = set()

    for c in retrieved_chunks:
        fname = c.get("filename", "").strip().lower()
        c_idx = c.get("chunk_index", 0)
        valid_files.add(fname)
        valid_pairs.add((fname, int(c_idx)))

    matches = CITATION_REGEX.findall(answer_text)

    validated: List[Dict[str, Any]] = []
    unverified: List[Dict[str, Any]] = []

    for filename_match, chunk_idx_match in matches:
        clean_file = filename_match.strip()
        clean_file_lower = clean_file.lower()
        chunk_idx = int(chunk_idx_match) if chunk_idx_match else None

        if chunk_idx is not None:
            if (clean_file_lower, chunk_idx) in valid_pairs:
                validated.append({
                    "filename": clean_file,
                    "chunk_index": chunk_idx,
                    "status": "VERIFIED_EXACT"
                })
            elif clean_file_lower in valid_files:
                unverified.append({
                    "filename": clean_file,
                    "chunk_index": chunk_idx,
                    "status": "UNVERIFIED_CHUNK_MISMATCH"
                })
            else:
                unverified.append({
                    "filename": clean_file,
                    "chunk_index": chunk_idx,
                    "status": "UNVERIFIED_SOURCE"
                })
        else:
            if clean_file_lower in valid_files:
                validated.append({
                    "filename": clean_file,
                    "chunk_index": None,
                    "status": "VERIFIED_FILE_ONLY"
                })
            else:
                unverified.append({
                    "filename": clean_file,
                    "chunk_index": None,
                    "status": "UNVERIFIED_SOURCE"
                })

    return {
        "validated_citations": validated,
        "unverified_citations": unverified,
        "has_valid_citations": len(validated) > 0 and len(unverified) == 0,
        "citation_count": len(matches),
        "valid_count": len(validated)
    }

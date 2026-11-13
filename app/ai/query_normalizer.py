"""Query normalization and terminology alignment for Sankalit Intelligence.
Maps everyday engineering and corporate phrases to canonical knowledge taxonomy terms.
"""

import re
from typing import Any, Dict, List

# Common synonym & colloquial mapping table
SYNONYM_MAPPINGS = [
    (r"\bairport work\b", "airport systems"),
    (r"\bairport tech\b", "airport technology systems"),
    (r"\bsound proofing\b", "sound isolation acoustic"),
    (r"\bauditorium sound\b", "auditorium acoustics"),
    (r"\belectrical drawings\b", "electrical power distribution MEP"),
    (r"\bhvac drawings\b", "HVAC mechanical MEP"),
    (r"\bleave policy\b", "leave and attendance policy HR"),
    (r"\bsalary slip\b", "compensation and payroll HR"),
    (r"\blux levels\b", "lighting illuminance specifications"),
    (r"\blighting plan\b", "architectural lighting design"),
    (r"\bprocurement rules\b", "procurement SOP vendor management"),
]


def normalize_query(query: str) -> Dict[str, Any]:
    """
    Clean and normalize user query:
    1. Removes excess whitespace and normalizes punctuation.
    2. Identifies colloquial synonyms and produces an expanded search representation.
    3. Preserves original user question intact.
    """
    clean_query = " ".join(query.strip().split())
    lower_query = clean_query.lower()

    expanded_terms: List[str] = []
    rewritten_query = clean_query

    for pattern, replacement in SYNONYM_MAPPINGS:
        if re.search(pattern, lower_query):
            expanded_terms.append(replacement)
            rewritten_query = re.sub(pattern, replacement, rewritten_query, flags=re.IGNORECASE)

    return {
        "original_query": clean_query,
        "normalized_query": clean_query.lower(),
        "rewritten_query": rewritten_query if rewritten_query != clean_query else clean_query,
        "expanded_terms": expanded_terms,
        "is_modified": rewritten_query != clean_query
    }


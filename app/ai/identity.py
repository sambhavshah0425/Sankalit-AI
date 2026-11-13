"""Centralized AI Identity definitions and dynamic company profile integration.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

AI_NAME = "Sankalit Intelligence"
AI_ROLE = "Internal AI Knowledge and Productivity Assistant for Sankalit Consultant"
ORGANIZATION_NAME = "Sankalit Consultant"

DEFAULT_COMPANY_PROFILE = {
    "company_name": "Sankalit Consultant",
    "company_description": (
        "Sankalit Consultant is a multidisciplinary engineering and consulting consultancy firm "
        "specializing in Acoustics, Audio-Visual Systems, Airport Systems, Architectural Lighting, "
        "Mechanical, Electrical, Plumbing (MEP), and Information Technology infrastructure design."
    ),
    "mission": (
        "Delivering state-of-the-art engineering consultancy and intelligent infrastructure design "
        "with precision, innovation, and technological excellence."
    ),
    "vision": (
        "To be a premier multidisciplinary engineering consultancy recognized globally for transformative "
        "infrastructure, technological integration, and sustainable design."
    ),
    "official_website": "https://sankalit.com",
    "contact_information": "info@sankalit.com",
    "practice_areas": [
        "Acoustics & Audio-Visual",
        "Airport Systems & Technology",
        "Information Technology & Networking",
        "Architectural Lighting Design",
        "MEP (Mechanical, Electrical, Plumbing, Fire Life Safety)",
        "Executive Management & Operations",
    ],
}


def get_company_profile(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Retrieve the official company profile record from the SQLite database.
    Falls back to structured default profile if the database table is empty or uninitialized.
    """
    from app.rag.vector_store import get_db
    try:
        with get_db(db_path) as conn:
            row = conn.execute(
                """
                SELECT id, company_name, company_description, mission, vision,
                       official_website, contact_information, additional_information_json, updated_at
                FROM company_profile
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()

            if not row:
                return dict(DEFAULT_COMPANY_PROFILE)

            profile = dict(row)
            # Parse additional information JSON
            extra_json = profile.get("additional_information_json")
            if extra_json:
                try:
                    profile["additional_information"] = json.loads(extra_json)
                except Exception:
                    profile["additional_information"] = {}
            else:
                profile["additional_information"] = {}

            profile["practice_areas"] = DEFAULT_COMPANY_PROFILE["practice_areas"]
            return profile
    except Exception:
        return dict(DEFAULT_COMPANY_PROFILE)


def get_ai_identity_summary(db_path: Optional[Path] = None) -> str:
    """Return a concise description of the assistant and the host consultancy firm."""
    profile = get_company_profile(db_path)
    return (
        f"{AI_NAME} is the official {AI_ROLE}. "
        f"{profile['company_name']} is an engineering consulting firm specializing in: "
        f"{', '.join(profile.get('practice_areas', []))}."
    )

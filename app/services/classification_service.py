"""Intelligent document classification service for Sankalit Intelligence.
Employs rule-based heuristics and domain terminology scoring to classify documents into
departments, domains, categories, and document types without unnecessary LLM overhead.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.ai.query_classifier import DOMAIN_PATTERNS
from app.rag.vector_store import get_db
from app.security.audit import log_audit_event

STATUS_UNCLASSIFIED = "UNCLASSIFIED"
STATUS_PENDING = "CLASSIFICATION_PENDING"
STATUS_CLASSIFIED = "CLASSIFIED"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_FAILED = "FAILED"

DOCUMENT_TYPE_PATTERNS = [
    (r"\bpolicy\b|\bhandbook\b|\bguideline\b|\bprotocol\b", "policy"),
    (r"\bspecification\b|\bspec\b|\btechnical specification\b|\bdbr\b", "technical_spec"),
    (r"\bproposal\b|\bbid\b|\brfp\b|\btender\b", "proposal"),
    (r"\bboq\b|\bbill of quantities\b|\bcost estimate\b|\bschedule of rates\b", "boq"),
    (r"\bsop\b|\bprocedure\b|\bstandard operating\b|\bchecklist\b", "sop"),
    (r"\bprogress report\b|\bsite visit\b|\binspection report\b|\bminutes of meeting\b|\bmom\b", "project_report"),
    (r"\bas-built\b|\bdrawing\b|\bschematic\b", "drawing_drawing"),
]

PROJECT_NAME_REGEX = re.compile(
    r"(?:project|proj(?:ect)?[\s:_-]+)([A-Z0-9][A-Za-z0-9_\-\s]{2,25})",
    re.IGNORECASE
)


def classify_document_content(
    text: str,
    filename: str,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Classify document into domain, category, department, and document_type using content scoring.
    Returns structured suggestion with confidence score and explanation.
    """
    combined_sample = f"{filename}\n{text[:4000]}".lower()

    # 1. Score Knowledge Domains
    domain_scores: Dict[str, int] = {}
    for domain_slug, patterns in DOMAIN_PATTERNS.items():
        score = 0
        for pat in patterns:
            matches = len(re.findall(pat, combined_sample))
            score += matches * 2
            # Bonus weight if keyword appears in filename
            if re.search(pat, filename.lower()):
                score += 5
        domain_scores[domain_slug] = score

    # Select top domain
    top_domain_slug = None
    top_domain_score = 0
    if domain_scores:
        top_domain_slug, top_domain_score = max(domain_scores.items(), key=lambda item: item[1])

    # 2. Determine Document Type
    detected_type = "general"
    for pat, dtype in DOCUMENT_TYPE_PATTERNS:
        if re.search(pat, combined_sample):
            detected_type = dtype
            break

    # 3. Detect Project Name
    detected_project = None
    proj_match = PROJECT_NAME_REGEX.search(text[:2000])
    if proj_match:
        detected_project = proj_match.group(1).strip()

    # 4. Resolve Domain and Category IDs from Database
    resolved_domain_id = None
    resolved_category_id = None
    resolved_department_id = None

    confidence = 0.0
    explanation = "Insufficient domain keywords found in text."

    if top_domain_score > 0 and top_domain_slug:
        confidence = min(0.95, 0.40 + (top_domain_score * 0.05))
        explanation = f"Matched {top_domain_score} occurrences of '{top_domain_slug}' domain keywords."

        with get_db(db_path) as conn:
            # Map domain slug to ID
            dom_row = conn.execute(
                "SELECT id FROM knowledge_domains WHERE slug = ?",
                (top_domain_slug,)
            ).fetchone()
            if dom_row:
                resolved_domain_id = dom_row["id"]

                # Find best matching category in this domain
                cat_rows = conn.execute(
                    "SELECT id, slug, name FROM knowledge_categories WHERE domain_id = ?",
                    (resolved_domain_id,)
                ).fetchall()

                best_cat_id = None
                best_cat_score = 0
                for c in cat_rows:
                    cat_slug_words = c["slug"].replace("-", " ").split()
                    cat_matches = sum(len(re.findall(r"\b" + re.escape(w) + r"\b", combined_sample)) for w in cat_slug_words)
                    if cat_matches > best_cat_score:
                        best_cat_score = cat_matches
                        best_cat_id = c["id"]

                resolved_category_id = best_cat_id or (cat_rows[0]["id"] if cat_rows else None)

            # Map to department if direct correspondence exists
            dept_code_map = {
                "hr": "HR",
                "it": "IT",
                "acoustic": "AV",
                "airport-systems": "AIRPORT",
                "lighting": "LIGHT",
                "mep": "MEP",
                "management": "MGMT",
                "operations": "ADMIN_GEN",
            }
            target_code = dept_code_map.get(top_domain_slug)
            if target_code:
                dept_row = conn.execute(
                    "SELECT id FROM departments WHERE code = ?",
                    (target_code,)
                ).fetchone()
                if dept_row:
                    resolved_department_id = dept_row["id"]

    # 5. Determine Classification Status
    if confidence >= 0.65:
        status = STATUS_CLASSIFIED
    elif confidence >= 0.35:
        status = STATUS_NEEDS_REVIEW
    else:
        status = STATUS_UNCLASSIFIED

    return {
        "domain_slug": top_domain_slug if top_domain_score > 0 else None,
        "domain_id": resolved_domain_id,
        "category_id": resolved_category_id,
        "department_id": resolved_department_id,
        "document_type": detected_type,
        "project_name": detected_project,
        "confidence": round(confidence, 2),
        "status": status,
        "explanation": explanation
    }


def update_document_classification(
    document_id: int,
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    document_type: Optional[str] = None,
    project_name: Optional[str] = None,
    project_identifier: Optional[str] = None,
    document_title: Optional[str] = None,
    status: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Manually correct or approve classification for a document."""
    with get_db(db_path) as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found.")

        new_domain = domain_id if domain_id is not None else doc["domain_id"]
        new_category = category_id if category_id is not None else doc["category_id"]
        new_type = document_type if document_type is not None else doc["document_type"]
        new_proj = project_name if project_name is not None else doc["project_name"]
        new_proj_id = project_identifier if project_identifier is not None else doc["project_identifier"]
        new_title = document_title if document_title is not None else doc["document_title"]
        new_status = status if status is not None else STATUS_CLASSIFIED

        conn.execute(
            """
            UPDATE documents
            SET domain_id = ?, category_id = ?, document_type = ?, project_name = ?,
                project_identifier = ?, document_title = ?, classification_status = ?,
                classification_confidence = 1.0, classification_explanation = 'Manually verified by administrator',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_domain, new_category, new_type, new_proj, new_proj_id, new_title, new_status, document_id)
        )
        conn.commit()

    if actor:
        log_audit_event(
            action="DOCUMENT_CLASSIFICATION_UPDATE",
            resource_type="DOCUMENT",
            resource_id=str(document_id),
            actor_id=actor.get("id"),
            actor_username=actor.get("username"),
            details={"status": new_status, "domain_id": new_domain, "category_id": new_category},
            db_path=db_path
        )

    from app.rag.vector_store import get_document
    return get_document(document_id, db_path=db_path) or {}


def approve_document_classification(
    document_id: int,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Approve a suggested document classification, marking it CLASSIFIED."""
    return update_document_classification(
        document_id=document_id,
        status=STATUS_CLASSIFIED,
        actor=actor,
        db_path=db_path
    )


def get_pending_classifications(
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieve documents awaiting classification review (NEEDS_REVIEW or UNCLASSIFIED)."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.filename, d.document_title, d.file_type, d.classification_status,
                   d.classification_confidence, d.classification_explanation,
                   d.domain_id, kd.name as domain_name,
                   d.category_id, kc.name as category_name,
                   d.document_type, d.project_name, d.created_at
            FROM documents d
            LEFT JOIN knowledge_domains kd ON kd.id = d.domain_id
            LEFT JOIN knowledge_categories kc ON kc.id = d.category_id
            WHERE d.status = 'active'
              AND d.classification_status IN ('NEEDS_REVIEW', 'UNCLASSIFIED', 'CLASSIFICATION_PENDING')
            ORDER BY d.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]


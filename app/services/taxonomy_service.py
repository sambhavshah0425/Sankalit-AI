"""Knowledge taxonomy management services for Sankalit Intelligence.
Provides CRUD and analytics for domains, categories, and company profile.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.vector_store import get_db
from app.security.audit import log_audit_event


def list_knowledge_domains(
    include_inactive: bool = False,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """List all knowledge domains with category counts and document counts."""
    with get_db(db_path) as conn:
        query = """
            SELECT d.id, d.name, d.slug, d.description, d.is_active, d.created_at, d.updated_at,
                   COUNT(DISTINCT c.id) as category_count,
                   COUNT(DISTINCT doc.id) as document_count
            FROM knowledge_domains d
            LEFT JOIN knowledge_categories c ON c.domain_id = d.id AND c.is_active = 1
            LEFT JOIN documents doc ON doc.domain_id = d.id AND doc.status = 'active'
        """
        if not include_inactive:
            query += " WHERE d.is_active = 1"
        query += " GROUP BY d.id ORDER BY d.id ASC"

        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]


def get_knowledge_domain(
    domain_id: int,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve domain details by ID including its categories."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, slug, description, is_active, created_at, updated_at
            FROM knowledge_domains
            WHERE id = ?
            """,
            (domain_id,)
        ).fetchone()

        if not row:
            return None

        domain = dict(row)
        cat_rows = conn.execute(
            """
            SELECT id, name, slug, description, is_active
            FROM knowledge_categories
            WHERE domain_id = ?
            ORDER BY id ASC
            """,
            (domain_id,)
        ).fetchall()
        domain["categories"] = [dict(c) for c in cat_rows]
        return domain


def get_knowledge_domain_by_slug(
    slug: str,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve domain details by unique slug."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, name, slug, description, is_active FROM knowledge_domains WHERE slug = ?",
            (slug.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None


def create_knowledge_domain(
    name: str,
    slug: str,
    description: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Create a new knowledge domain (requires taxonomy:manage permission)."""
    clean_name = name.strip()
    clean_slug = slug.strip().lower()

    if not clean_name or not clean_slug:
        raise ValueError("Domain name and slug are required.")

    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM knowledge_domains WHERE slug = ? OR name = ?",
            (clean_slug, clean_name)
        ).fetchone()
        if existing:
            raise ValueError(f"Domain with slug '{clean_slug}' or name '{clean_name}' already exists.")

        cursor = conn.execute(
            """
            INSERT INTO knowledge_domains (name, slug, description)
            VALUES (?, ?, ?)
            """,
            (clean_name, clean_slug, description)
        )
        domain_id = cursor.lastrowid
        conn.commit()

    if actor:
        log_audit_event(
            action="DOMAIN_CREATE",
            resource_type="TAXONOMY",
            resource_id=str(domain_id),
            actor_id=actor.get("id"),
            actor_username=actor.get("username"),
            details={"name": clean_name, "slug": clean_slug},
            db_path=db_path
        )

    return get_knowledge_domain(domain_id, db_path=db_path) or {}


def update_knowledge_domain(
    domain_id: int,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Update domain attributes."""
    with get_db(db_path) as conn:
        current = conn.execute(
            "SELECT id, name, slug, description, is_active FROM knowledge_domains WHERE id = ?",
            (domain_id,)
        ).fetchone()
        if not current:
            raise ValueError(f"Knowledge domain with ID {domain_id} not found.")

        new_name = name.strip() if name is not None else current["name"]
        new_slug = slug.strip().lower() if slug is not None else current["slug"]
        new_desc = description if description is not None else current["description"]
        new_active = int(is_active) if is_active is not None else current["is_active"]

        conn.execute(
            """
            UPDATE knowledge_domains
            SET name = ?, slug = ?, description = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_name, new_slug, new_desc, new_active, domain_id)
        )
        conn.commit()

    if actor:
        log_audit_event(
            action="DOMAIN_UPDATE",
            resource_type="TAXONOMY",
            resource_id=str(domain_id),
            actor_id=actor.get("id"),
            actor_username=actor.get("username"),
            details={"name": new_name, "slug": new_slug, "is_active": new_active},
            db_path=db_path
        )

    return get_knowledge_domain(domain_id, db_path=db_path) or {}


def deactivate_knowledge_domain(
    domain_id: int,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Deactivate domain without deleting associated historical documents."""
    return bool(update_knowledge_domain(domain_id, is_active=False, actor=actor, db_path=db_path))


def list_knowledge_categories(
    domain_id: Optional[int] = None,
    include_inactive: bool = False,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """List knowledge categories optionally filtered by domain_id."""
    with get_db(db_path) as conn:
        query = """
            SELECT c.id, c.domain_id, c.name, c.slug, c.description, c.is_active,
                   d.name as domain_name, d.slug as domain_slug,
                   COUNT(doc.id) as document_count
            FROM knowledge_categories c
            JOIN knowledge_domains d ON d.id = c.domain_id
            LEFT JOIN documents doc ON doc.category_id = c.id AND doc.status = 'active'
            WHERE 1=1
        """
        params: List[Any] = []
        if domain_id is not None:
            query += " AND c.domain_id = ?"
            params.append(domain_id)
        if not include_inactive:
            query += " AND c.is_active = 1"

        query += " GROUP BY c.id ORDER BY c.domain_id ASC, c.id ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_knowledge_category(
    category_id: int,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve a single category by ID."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.id, c.domain_id, c.name, c.slug, c.description, c.is_active,
                   d.name as domain_name, d.slug as domain_slug
            FROM knowledge_categories c
            JOIN knowledge_domains d ON d.id = c.domain_id
            WHERE c.id = ?
            """,
            (category_id,)
        ).fetchone()
        return dict(row) if row else None


def create_knowledge_category(
    domain_id: int,
    name: str,
    slug: str,
    description: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Create a new knowledge category within a domain."""
    clean_name = name.strip()
    clean_slug = slug.strip().lower()

    if not clean_name or not clean_slug:
        raise ValueError("Category name and slug are required.")

    with get_db(db_path) as conn:
        # Check domain existence
        dom = conn.execute("SELECT id FROM knowledge_domains WHERE id = ?", (domain_id,)).fetchone()
        if not dom:
            raise ValueError(f"Parent domain with ID {domain_id} does not exist.")

        existing = conn.execute(
            "SELECT id FROM knowledge_categories WHERE domain_id = ? AND slug = ?",
            (domain_id, clean_slug)
        ).fetchone()
        if existing:
            raise ValueError(f"Category slug '{clean_slug}' already exists under domain {domain_id}.")

        cursor = conn.execute(
            """
            INSERT INTO knowledge_categories (domain_id, name, slug, description)
            VALUES (?, ?, ?, ?)
            """,
            (domain_id, clean_name, clean_slug, description)
        )
        cat_id = cursor.lastrowid
        conn.commit()

    if actor:
        log_audit_event(
            action="CATEGORY_CREATE",
            resource_type="TAXONOMY",
            resource_id=str(cat_id),
            actor_id=actor.get("id"),
            actor_username=actor.get("username"),
            details={"name": clean_name, "slug": clean_slug, "domain_id": domain_id},
            db_path=db_path
        )

    return get_knowledge_category(cat_id, db_path=db_path) or {}


def update_knowledge_category(
    category_id: int,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Update category details."""
    with get_db(db_path) as conn:
        current = conn.execute(
            "SELECT id, domain_id, name, slug, description, is_active FROM knowledge_categories WHERE id = ?",
            (category_id,)
        ).fetchone()
        if not current:
            raise ValueError(f"Knowledge category with ID {category_id} not found.")

        new_name = name.strip() if name is not None else current["name"]
        new_slug = slug.strip().lower() if slug is not None else current["slug"]
        new_desc = description if description is not None else current["description"]
        new_active = int(is_active) if is_active is not None else current["is_active"]

        conn.execute(
            """
            UPDATE knowledge_categories
            SET name = ?, slug = ?, description = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_name, new_slug, new_desc, new_active, category_id)
        )
        conn.commit()

    if actor:
        log_audit_event(
            action="CATEGORY_UPDATE",
            resource_type="TAXONOMY",
            resource_id=str(category_id),
            actor_id=actor.get("id"),
            actor_username=actor.get("username"),
            details={"name": new_name, "slug": new_slug, "is_active": new_active},
            db_path=db_path
        )

    return get_knowledge_category(category_id, db_path=db_path) or {}


def deactivate_knowledge_category(
    category_id: int,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Deactivate category without deleting associated historical documents."""
    return bool(update_knowledge_category(category_id, is_active=False, actor=actor, db_path=db_path))


def update_company_profile(
    company_name: Optional[str] = None,
    company_description: Optional[str] = None,
    mission: Optional[str] = None,
    vision: Optional[str] = None,
    official_website: Optional[str] = None,
    contact_information: Optional[str] = None,
    additional_information: Optional[Dict[str, Any]] = None,
    actor: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Update official company profile record (requires company_profile:update permission)."""
    with get_db(db_path) as conn:
        current = conn.execute("SELECT * FROM company_profile ORDER BY id ASC LIMIT 1").fetchone()
        if not current:
            # Insert initial record if not exists
            conn.execute(
                """
                INSERT INTO company_profile (
                    company_name, company_description, mission, vision,
                    official_website, contact_information, additional_information_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_name or "Sankalit Consultant",
                    company_description or "",
                    mission or "",
                    vision or "",
                    official_website or "",
                    contact_information or "",
                    json.dumps(additional_information or {})
                )
            )
        else:
            new_name = company_name if company_name is not None else current["company_name"]
            new_desc = company_description if company_description is not None else current["company_description"]
            new_mission = mission if mission is not None else current["mission"]
            new_vision = vision if vision is not None else current["vision"]
            new_site = official_website if official_website is not None else current["official_website"]
            new_contact = contact_information if contact_information is not None else current["contact_information"]
            new_extra = (
                json.dumps(additional_information) if additional_information is not None
                else current["additional_information_json"]
            )

            conn.execute(
                """
                UPDATE company_profile
                SET company_name = ?, company_description = ?, mission = ?, vision = ?,
                    official_website = ?, contact_information = ?, additional_information_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_name, new_desc, new_mission, new_vision, new_site, new_contact, new_extra, current["id"])
            )
        conn.commit()

    if actor:
        log_audit_event(
            action="COMPANY_PROFILE_UPDATE",
            resource_type="COMPANY_PROFILE",
            actor_id=actor.get("id"),
            actor_username=actor.get("username"),
            details={"company_name": company_name},
            db_path=db_path
        )

    from app.ai.identity import get_company_profile
    return get_company_profile(db_path=db_path)


def get_taxonomy_statistics(
    allowed_document_ids: Optional[List[int]] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Retrieve comprehensive knowledge base statistics.
    Filters strictly to allowed_document_ids to avoid leaking metadata about restricted documents.
    """
    with get_db(db_path) as conn:
        doc_where = "WHERE status = 'active'"
        doc_params: List[Any] = []
        if allowed_document_ids is not None:
            if not allowed_document_ids:
                return {
                    "total_documents": 0,
                    "total_chunks": 0,
                    "documents_by_domain": [],
                    "documents_by_department": [],
                    "documents_by_type": [],
                    "documents_by_classification_status": [],
                    "active_versions": 0
                }
            placeholders = ",".join("?" for _ in allowed_document_ids)
            doc_where += f" AND id IN ({placeholders})"
            doc_params.extend(allowed_document_ids)

        total_docs = conn.execute(
            f"SELECT COUNT(*) FROM documents {doc_where}",
            doc_params
        ).fetchone()[0]

        # Total chunks for allowed documents
        chunk_query = f"""
            SELECT COUNT(*) FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            {doc_where.replace('status', 'd.status').replace('id IN', 'd.id IN')}
        """
        total_chunks = conn.execute(chunk_query, doc_params).fetchone()[0]

        # Docs by domain
        dom_query = f"""
            SELECT COALESCE(kd.name, 'Unassigned') as domain_name,
                   COALESCE(kd.slug, 'unassigned') as domain_slug,
                   COUNT(d.id) as count
            FROM documents d
            LEFT JOIN knowledge_domains kd ON kd.id = d.domain_id
            {doc_where}
            GROUP BY d.domain_id
            ORDER BY count DESC
        """
        docs_by_domain = [dict(r) for r in conn.execute(dom_query, doc_params).fetchall()]

        # Docs by department
        dept_query = f"""
            SELECT dept.name as department_name, dept.code as department_code, COUNT(d.id) as count
            FROM documents d
            JOIN document_departments dd ON dd.document_id = d.id
            JOIN departments dept ON dept.id = dd.department_id
            {doc_where}
            GROUP BY dept.id
            ORDER BY count DESC
        """
        docs_by_dept = [dict(r) for r in conn.execute(dept_query, doc_params).fetchall()]

        # Docs by type
        type_query = f"""
            SELECT COALESCE(document_type, 'general') as document_type, COUNT(id) as count
            FROM documents
            {doc_where}
            GROUP BY document_type
            ORDER BY count DESC
        """
        docs_by_type = [dict(r) for r in conn.execute(type_query, doc_params).fetchall()]

        # Docs by classification status
        class_query = f"""
            SELECT COALESCE(classification_status, 'UNCLASSIFIED') as status, COUNT(id) as count
            FROM documents
            {doc_where}
            GROUP BY classification_status
        """
        docs_by_class = [dict(r) for r in conn.execute(class_query, doc_params).fetchall()]

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "documents_by_domain": docs_by_domain,
            "documents_by_department": docs_by_dept,
            "documents_by_type": docs_by_type,
            "documents_by_classification_status": docs_by_class,
            "active_versions": total_docs
        }

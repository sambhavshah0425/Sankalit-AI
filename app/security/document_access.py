from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.rag.vector_store import get_db
from app.security.rbac import ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE

VISIBILITY_PUBLIC = "PUBLIC"
VISIBILITY_COMPANY = "COMPANY"
VISIBILITY_DEPARTMENT = "DEPARTMENT"
VISIBILITY_RESTRICTED = "RESTRICTED"

VALID_VISIBILITIES = {
    VISIBILITY_PUBLIC,
    VISIBILITY_COMPANY,
    VISIBILITY_DEPARTMENT,
    VISIBILITY_RESTRICTED,
}


def get_authorized_document_ids(
    user: Dict[str, Any],
    db_path: Optional[Path] = None
) -> List[int]:
    """
    Compute the strict list of document IDs the given user is authorized to read or query.
    Enforces least privilege at the SQL layer before any embeddings or chunks are retrieved.

    Rules:
    1. SUPER_ADMIN / is_superuser: All documents.
    2. Document Owner: Documents where owner_id = user_id.
    3. PUBLIC visibility: Any authenticated user.
    4. COMPANY visibility: Any active user with EMPLOYEE, MANAGER, or ADMIN roles.
    5. DEPARTMENT visibility: Documents matching at least one of the user's assigned departments.
    6. RESTRICTED / Explicit: Document has an explicit grant in document_permissions for user_id or user's roles.
    """
    user_id = user.get("id")
    roles = user.get("roles", [])
    is_superuser = user.get("is_superuser", False)

    with get_db(db_path) as conn:
        # SUPER_ADMIN bypass
        if is_superuser or ROLE_SUPER_ADMIN in roles:
            rows = conn.execute("SELECT id FROM documents WHERE status = 'active'").fetchall()
            return [row["id"] for row in rows]

        # Retrieve user's department IDs
        user_dept_rows = conn.execute(
            "SELECT department_id FROM user_departments WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        user_dept_ids = [r["department_id"] for r in user_dept_rows]

        # Retrieve user's role IDs
        role_rows = conn.execute(
            """
            SELECT r.id FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = ?
            """,
            (user_id,)
        ).fetchall()
        user_role_ids = [r["id"] for r in role_rows]

        authorized_ids: Set[int] = set()

        # 1. Documents owned by the user
        owner_rows = conn.execute(
            "SELECT id FROM documents WHERE owner_id = ? AND status = 'active'",
            (user_id,)
        ).fetchall()
        for r in owner_rows:
            authorized_ids.add(r["id"])

        # 2. PUBLIC documents
        public_rows = conn.execute(
            "SELECT id FROM documents WHERE visibility = 'PUBLIC' AND status = 'active'"
        ).fetchall()
        for r in public_rows:
            authorized_ids.add(r["id"])

        # 3. COMPANY documents (for company members: EMPLOYEE, MANAGER, ADMIN)
        is_company_member = any(r in (ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE) for r in roles)
        if is_company_member:
            company_rows = conn.execute(
                "SELECT id FROM documents WHERE visibility = 'COMPANY' AND status = 'active'"
            ).fetchall()
            for r in company_rows:
                authorized_ids.add(r["id"])

        # 4. DEPARTMENT documents matching user departments
        if user_dept_ids:
            placeholders = ",".join("?" for _ in user_dept_ids)
            dept_docs = conn.execute(
                f"""
                SELECT DISTINCT d.id
                FROM documents d
                JOIN document_departments dd ON dd.document_id = d.id
                WHERE d.visibility = 'DEPARTMENT'
                  AND d.status = 'active'
                  AND dd.department_id IN ({placeholders})
                """,
                user_dept_ids
            ).fetchall()
            for r in dept_docs:
                authorized_ids.add(r["id"])

        # 5. Explicit user or role grants in document_permissions
        query = """
            SELECT DISTINCT d.id
            FROM documents d
            JOIN document_permissions dp ON dp.document_id = d.id
            WHERE d.status = 'active'
              AND (dp.user_id = ?
        """
        params: List[Any] = [user_id]
        if user_role_ids:
            role_placeholders = ",".join("?" for _ in user_role_ids)
            query += f" OR dp.role_id IN ({role_placeholders})"
            params.extend(user_role_ids)
        query += ")"

        explicit_rows = conn.execute(query, params).fetchall()
        for r in explicit_rows:
            authorized_ids.add(r["id"])

        return sorted(list(authorized_ids))


def can_user_read_document(
    user: Dict[str, Any],
    document_id: int,
    db_path: Optional[Path] = None
) -> bool:
    """Check if the user is authorized to view or query the specific document."""
    allowed_ids = get_authorized_document_ids(user, db_path=db_path)
    return document_id in allowed_ids


def can_user_manage_document(
    user: Dict[str, Any],
    document_id: int,
    db_path: Optional[Path] = None
) -> bool:
    """
    Check if the user has administrative/write rights to manage or delete a document.
    Authorized if:
    - User has SUPER_ADMIN or ADMIN role.
    - User is the owner of the document.
    - User has explicit 'write' or 'admin' grant in document_permissions.
    """
    user_id = user.get("id")
    roles = user.get("roles", [])
    if user.get("is_superuser", False) or ROLE_SUPER_ADMIN in roles or ROLE_ADMIN in roles:
        return True

    with get_db(db_path) as conn:
        doc = conn.execute(
            "SELECT owner_id FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        if not doc:
            return False

        if doc["owner_id"] == user_id:
            return True

        # Check explicit permission
        perm = conn.execute(
            """
            SELECT id FROM document_permissions
            WHERE document_id = ? AND user_id = ? AND permission_type IN ('write', 'admin')
            """,
            (document_id, user_id)
        ).fetchone()

        return perm is not None


def set_document_departments(
    document_id: int,
    department_ids: List[int],
    db_path: Optional[Path] = None
) -> None:
    """Assign departments to a document."""
    with get_db(db_path) as conn:
        conn.execute(
            "DELETE FROM document_departments WHERE document_id = ?",
            (document_id,)
        )
        for dept_id in department_ids:
            conn.execute(
                """
                INSERT OR IGNORE INTO document_departments (document_id, department_id)
                VALUES (?, ?)
                """,
                (document_id, dept_id)
            )
        conn.commit()


def get_document_departments(
    document_id: int,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Get all departments associated with a document."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.name, d.code
            FROM departments d
            JOIN document_departments dd ON dd.department_id = d.id
            WHERE dd.document_id = ?
            """,
            (document_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_document_permissions(
    document_id: int,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieve explicit permission records for a document."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT dp.id, dp.document_id, dp.user_id, u.username, dp.role_id, r.name as role_name,
                   dp.permission_type, dp.created_at
            FROM document_permissions dp
            LEFT JOIN users u ON u.id = dp.user_id
            LEFT JOIN roles r ON r.id = dp.role_id
            WHERE dp.document_id = ?
            """,
            (document_id,)
        ).fetchall()
        return [dict(row) for row in rows]


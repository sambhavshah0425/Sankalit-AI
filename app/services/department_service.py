from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.vector_store import get_db
from app.security.audit import log_audit_event


def list_departments(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve all corporate departments with member counts."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.name, d.code, d.description, d.created_at,
                   COUNT(ud.user_id) as member_count
            FROM departments d
            LEFT JOIN user_departments ud ON ud.department_id = d.id
            GROUP BY d.id
            ORDER BY d.name ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_department(department_id: int, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve details for a single department."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT d.id, d.name, d.code, d.description, d.created_at,
                   COUNT(ud.user_id) as member_count
            FROM departments d
            LEFT JOIN user_departments ud ON ud.department_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
            """,
            (department_id,)
        ).fetchone()
        return dict(row) if row else None


def create_department(
    name: str,
    code: str,
    description: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Create a new department."""
    clean_name = name.strip()
    clean_code = code.strip().upper()

    if not clean_name or not clean_code:
        raise ValueError("Department name and code are required.")

    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM departments WHERE name = ? OR code = ?",
            (clean_name, clean_code)
        ).fetchone()

        if existing:
            raise ValueError(f"Department with name '{clean_name}' or code '{clean_code}' already exists.")

        cursor = conn.execute(
            "INSERT INTO departments (name, code, description) VALUES (?, ?, ?)",
            (clean_name, clean_code, description)
        )
        dept_id = cursor.lastrowid
        conn.commit()

    if actor:
        log_audit_event(
            action="DEPARTMENT_CREATE",
            resource_type="DEPARTMENT",
            actor_id=actor["id"],
            actor_username=actor["username"],
            resource_id=str(dept_id),
            details={"name": clean_name, "code": clean_code},
            ip_address=ip_address,
            status="SUCCESS",
            db_path=db_path
        )

    return {
        "id": dept_id,
        "name": clean_name,
        "code": clean_code,
        "description": description
    }


def assign_user_to_department(
    user_id: int,
    department_id: int,
    is_primary: bool = False,
    actor: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Assign a user to a department."""
    with get_db(db_path) as conn:
        user = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        dept = conn.execute("SELECT id, name FROM departments WHERE id = ?", (department_id,)).fetchone()
        if not dept:
            raise ValueError(f"Department with ID {department_id} not found.")

        conn.execute(
            """
            INSERT INTO user_departments (user_id, department_id, is_primary)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, department_id) DO UPDATE SET is_primary = excluded.is_primary
            """,
            (user_id, department_id, 1 if is_primary else 0)
        )
        conn.commit()

    if actor:
        log_audit_event(
            action="USER_DEPARTMENT_ASSIGN",
            resource_type="USER_DEPARTMENT",
            actor_id=actor["id"],
            actor_username=actor["username"],
            resource_id=f"user:{user_id}_dept:{department_id}",
            details={"username": user["username"], "department_name": dept["name"], "is_primary": is_primary},
            ip_address=ip_address,
            status="SUCCESS",
            db_path=db_path
        )

    return True


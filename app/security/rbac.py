from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.rag.vector_store import get_db

ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_ADMIN = "ADMIN"
ROLE_MANAGER = "MANAGER"
ROLE_EMPLOYEE = "EMPLOYEE"
ROLE_VIEWER = "VIEWER"

SYSTEM_ROLES = {
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_EMPLOYEE,
    ROLE_VIEWER
}


def get_user_roles(user_id: int, db_path: Optional[Path] = None) -> List[str]:
    """Retrieve all assigned role names for a user."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = ?
            """,
            (user_id,)
        ).fetchall()
        return [row["name"] for row in rows]


def get_user_permissions(user_id: int, db_path: Optional[Path] = None) -> Set[str]:
    """
    Retrieve the union of all permissions granted to a user across all their assigned roles.
    If the user has SUPER_ADMIN role or is_superuser, all permissions are granted.
    """
    with get_db(db_path) as conn:
        user = conn.execute("SELECT is_superuser FROM users WHERE id = ?", (user_id,)).fetchone()
        if user and user["is_superuser"]:
            all_perms = conn.execute("SELECT name FROM permissions").fetchall()
            return {p["name"] for p in all_perms}

        roles = get_user_roles(user_id, db_path)
        if ROLE_SUPER_ADMIN in roles:
            all_perms = conn.execute("SELECT name FROM permissions").fetchall()
            return {p["name"] for p in all_perms}

        rows = conn.execute(
            """
            SELECT DISTINCT p.name
            FROM permissions p
            JOIN role_permissions rp ON rp.permission_id = p.id
            JOIN user_roles ur ON ur.role_id = rp.role_id
            WHERE ur.user_id = ?
            """,
            (user_id,)
        ).fetchall()
        return {row["name"] for row in rows}


def get_user_departments(user_id: int, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve list of departments a user belongs to."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.name, d.code, ud.is_primary
            FROM departments d
            JOIN user_departments ud ON ud.department_id = d.id
            WHERE ud.user_id = ?
            """,
            (user_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def user_has_permission(
    user_roles: List[str],
    user_permissions: Set[str],
    required_permission: str
) -> bool:
    """Check if the user possesses the required permission or super-admin privilege."""
    if ROLE_SUPER_ADMIN in user_roles:
        return True
    return required_permission in user_permissions


def can_actor_manage_target_role(actor_roles: List[str], target_role: str) -> bool:
    """
    Prevent privilege escalation:
    - Only SUPER_ADMIN can assign or modify SUPER_ADMIN or ADMIN roles.
    - ADMIN can assign or modify MANAGER, EMPLOYEE, VIEWER.
    - Other roles cannot assign or manage roles.
    """
    if ROLE_SUPER_ADMIN in actor_roles:
        return True

    if ROLE_ADMIN in actor_roles:
        return target_role not in (ROLE_SUPER_ADMIN, ROLE_ADMIN)

    return False


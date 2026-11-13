from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.vector_store import get_db
from app.security.audit import log_audit_event
from app.security.rbac import (
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    can_actor_manage_target_role,
    get_user_departments,
    get_user_permissions,
    get_user_roles,
)


def list_users(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List all registered users with their roles and department memberships."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, username, email, full_name, is_active, is_superuser,
                   failed_login_attempts, locked_until, created_at, updated_at
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()

        results = []
        for r in rows:
            u_dict = dict(r)
            u_dict["roles"] = get_user_roles(r["id"], db_path)
            u_dict["departments"] = get_user_departments(r["id"], db_path)
            results.append(u_dict)
        return results


def get_user_by_id(user_id: int, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve user details by ID."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, username, email, full_name, is_active, is_superuser,
                   failed_login_attempts, locked_until, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if not row:
            return None

        u_dict = dict(row)
        u_dict["roles"] = get_user_roles(user_id, db_path)
        u_dict["departments"] = get_user_departments(user_id, db_path)
        u_dict["permissions"] = list(get_user_permissions(user_id, db_path))
        return u_dict


def update_user(
    actor: Dict[str, Any],
    target_user_id: int,
    full_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    roles: Optional[List[str]] = None,
    department_ids: Optional[List[int]] = None,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Update user profile, status, roles, and departments.
    Enforces role hierarchy (ADMIN cannot modify SUPER_ADMIN or grant SUPER_ADMIN).
    """
    with get_db(db_path) as conn:
        target_user = conn.execute(
            "SELECT id, username, is_superuser FROM users WHERE id = ?",
            (target_user_id,)
        ).fetchone()

        if not target_user:
            raise ValueError(f"User with ID {target_user_id} not found.")

        actor_roles = actor.get("roles", [])
        is_actor_super = actor.get("is_superuser") or ROLE_SUPER_ADMIN in actor_roles

        # Protect SUPER_ADMIN
        if target_user["is_superuser"] and not is_actor_super:
            raise PermissionError("Only Super Administrators can modify Super Administrator accounts.")

        # Update basic profile
        if full_name is not None:
            conn.execute(
                "UPDATE users SET full_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (full_name, target_user_id)
            )

        if is_active is not None:
            # Prevent deactivating the last active SUPER_ADMIN
            if not is_active and target_user["is_superuser"]:
                active_supers = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE is_superuser = 1 AND is_active = 1"
                ).fetchone()[0]
                if active_supers <= 1:
                    raise ValueError("Cannot deactivate the sole Super Administrator account.")

            conn.execute(
                "UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (1 if is_active else 0, target_user_id)
            )

        # Update roles if specified
        if roles is not None:
            for r in roles:
                if not can_actor_manage_target_role(actor_roles, r):
                    raise PermissionError(f"Insufficient privileges to assign role '{r}'.")

            conn.execute("DELETE FROM user_roles WHERE user_id = ?", (target_user_id,))
            for r_name in roles:
                r_row = conn.execute("SELECT id FROM roles WHERE name = ?", (r_name,)).fetchone()
                if r_row:
                    conn.execute(
                        "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
                        (target_user_id, r_row["id"])
                    )

            # Update is_superuser flag
            is_super = 1 if ROLE_SUPER_ADMIN in roles else 0
            conn.execute("UPDATE users SET is_superuser = ? WHERE id = ?", (is_super, target_user_id))

        # Update departments if specified
        if department_ids is not None:
            conn.execute("DELETE FROM user_departments WHERE user_id = ?", (target_user_id,))
            for dept_id in department_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?, ?)",
                    (target_user_id, dept_id)
                )

        conn.commit()

    log_audit_event(
        action="USER_UPDATE",
        resource_type="USER",
        actor_id=actor["id"],
        actor_username=actor["username"],
        resource_id=str(target_user_id),
        details={"roles": roles, "is_active": is_active, "department_ids": department_ids},
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )

    return get_user_by_id(target_user_id, db_path)


def delete_user(
    actor: Dict[str, Any],
    target_user_id: int,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """
    Delete a user account.
    Prevents self-deletion of last SUPER_ADMIN.
    """
    with get_db(db_path) as conn:
        target_user = conn.execute(
            "SELECT id, username, is_superuser FROM users WHERE id = ?",
            (target_user_id,)
        ).fetchone()

        if not target_user:
            raise ValueError(f"User with ID {target_user_id} not found.")

        if target_user["is_superuser"]:
            active_supers = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_superuser = 1"
            ).fetchone()[0]
            if active_supers <= 1:
                raise ValueError("Cannot delete the sole Super Administrator account.")

        conn.execute("DELETE FROM users WHERE id = ?", (target_user_id,))
        conn.commit()

    log_audit_event(
        action="USER_DELETE",
        resource_type="USER",
        actor_id=actor["id"],
        actor_username=actor["username"],
        resource_id=str(target_user_id),
        details={"deleted_username": target_user["username"]},
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )
    return True


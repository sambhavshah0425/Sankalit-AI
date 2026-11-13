from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import ALLOW_OPEN_REGISTRATION
from app.rag.vector_store import get_db
from app.security.audit import log_audit_event
from app.security.passwords import (
    check_account_lockout,
    hash_password,
    record_failed_login,
    reset_failed_logins,
    validate_password_strength,
    verify_password,
)
from app.security.rbac import (
    ROLE_SUPER_ADMIN,
    ROLE_EMPLOYEE,
    can_actor_manage_target_role,
    get_user_departments,
    get_user_permissions,
    get_user_roles,
)
from app.security.tokens import (
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)


def register_user(
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    requested_roles: Optional[List[str]] = None,
    department_ids: Optional[List[int]] = None,
    actor: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Register a new user account:
    - If 0 users exist, the first registered user is automatically created as SUPER_ADMIN.
    - Subsequent registrations require ALLOW_OPEN_REGISTRATION or must be invoked by an authorized admin.
    - Enforces role assignment boundaries (prevents privilege escalation).
    """
    clean_username = username.strip().lower()
    clean_email = email.strip().lower()

    if not clean_username or not clean_email:
        raise ValueError("Username and email are required.")

    valid, err_msg = validate_password_strength(password)
    if not valid:
        raise ValueError(err_msg)

    with get_db(db_path) as conn:
        # Check uniqueness
        existing = conn.execute(
            "SELECT id, username, email FROM users WHERE username = ? OR email = ?",
            (clean_username, clean_email)
        ).fetchone()

        if existing:
            if existing["username"] == clean_username:
                raise ValueError(f"Username '{clean_username}' already exists.")
            raise ValueError(f"Email '{clean_email}' already registered.")

        # Check total user count and whether a SUPER_ADMIN already exists to determine initial bootstrap
        superadmin_exists = conn.execute(
            """
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE r.name = ?
            LIMIT 1
            """,
            (ROLE_SUPER_ADMIN,)
        ).fetchone()

        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        is_bootstrap = (total_users == 0 and not superadmin_exists)

        if not is_bootstrap:
            # If not bootstrap, public or unprivileged users can NEVER claim SUPER_ADMIN
            if requested_roles and ROLE_SUPER_ADMIN in requested_roles:
                if not actor or ROLE_SUPER_ADMIN not in actor.get("roles", []):
                    raise PermissionError("Only existing Super Administrators can grant the SUPER_ADMIN role.")

            if not ALLOW_OPEN_REGISTRATION:
                if not actor or not any(r in (ROLE_SUPER_ADMIN, "ADMIN") for r in actor.get("roles", [])):
                    raise PermissionError("Public registration is disabled. Administrator authorization required.")

        # Determine roles
        assigned_roles: List[str] = []
        is_superuser = 0

        if is_bootstrap:
            assigned_roles = [ROLE_SUPER_ADMIN]
            is_superuser = 1
        elif requested_roles:
            actor_roles = actor.get("roles", []) if actor else []
            for r in requested_roles:
                if not can_actor_manage_target_role(actor_roles, r):
                    raise PermissionError(f"Insufficient privileges to assign role '{r}'.")
                assigned_roles.append(r)
        else:
            assigned_roles = [ROLE_EMPLOYEE]

        hashed_pw = hash_password(password)

        cursor = conn.execute(
            """
            INSERT INTO users (username, email, hashed_password, full_name, is_superuser)
            VALUES (?, ?, ?, ?, ?)
            """,
            (clean_username, clean_email, hashed_pw, full_name, is_superuser)
        )
        user_id = cursor.lastrowid

        # Assign roles
        for r_name in assigned_roles:
            role_row = conn.execute("SELECT id FROM roles WHERE name = ?", (r_name,)).fetchone()
            if role_row:
                conn.execute(
                    "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
                    (user_id, role_row["id"])
                )

        # Assign departments
        if department_ids:
            for dept_id in department_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?, ?)",
                    (user_id, dept_id)
                )

        conn.commit()

    log_audit_event(
        action="USER_REGISTER",
        resource_type="USER",
        actor_id=actor["id"] if actor else user_id,
        actor_username=actor["username"] if actor else clean_username,
        resource_id=str(user_id),
        details={"username": clean_username, "roles": assigned_roles, "bootstrap": is_bootstrap},
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )

    return {
        "id": user_id,
        "username": clean_username,
        "email": clean_email,
        "full_name": full_name,
        "roles": assigned_roles,
        "is_active": True,
        "is_superuser": bool(is_superuser)
    }


def authenticate_user(
    username_or_email: str,
    password: str,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Tuple[Dict[str, Any], str, str]:
    """
    Authenticate user credentials, check lockout, and issue access/refresh tokens.
    Returns (user_dict, access_token, raw_refresh_token).
    """
    identifier = username_or_email.strip().lower()

    with get_db(db_path) as conn:
        user = conn.execute(
            """
            SELECT id, username, email, full_name, hashed_password, is_active,
                   is_superuser, failed_login_attempts, locked_until
            FROM users
            WHERE username = ? OR email = ?
            """,
            (identifier, identifier)
        ).fetchone()

        if not user:
            log_audit_event(
                action="LOGIN_FAILED",
                resource_type="AUTH",
                actor_username=identifier,
                details={"reason": "User not found"},
                ip_address=ip_address,
                status="FAILURE",
                db_path=db_path
            )
            raise ValueError("Invalid username or password.")

        user_id = user["id"]

        if not user["is_active"]:
            log_audit_event(
                action="LOGIN_BLOCKED",
                resource_type="AUTH",
                actor_id=user_id,
                actor_username=user["username"],
                details={"reason": "Account deactivated"},
                ip_address=ip_address,
                status="FAILURE",
                db_path=db_path
            )
            raise PermissionError("Account is deactivated. Contact an administrator.")

        is_locked, lock_msg = check_account_lockout(user)
        if is_locked:
            log_audit_event(
                action="LOGIN_BLOCKED",
                resource_type="AUTH",
                actor_id=user_id,
                actor_username=user["username"],
                details={"reason": "Account locked due to consecutive failures"},
                ip_address=ip_address,
                status="FAILURE",
                db_path=db_path
            )
            raise PermissionError(lock_msg)

        if not verify_password(password, user["hashed_password"]):
            record_failed_login(user_id, db_path=db_path)
            log_audit_event(
                action="LOGIN_FAILED",
                resource_type="AUTH",
                actor_id=user_id,
                actor_username=user["username"],
                details={"reason": "Incorrect password"},
                ip_address=ip_address,
                status="FAILURE",
                db_path=db_path
            )
            raise ValueError("Invalid username or password.")

    # Reset failed attempts upon successful authentication
    reset_failed_logins(user_id, db_path=db_path)

    roles = get_user_roles(user_id, db_path=db_path)
    departments = get_user_departments(user_id, db_path=db_path)
    permissions = get_user_permissions(user_id, db_path=db_path)

    access_token = create_access_token(
        user_id=user_id,
        username=user["username"],
        email=user["email"],
        roles=roles
    )
    refresh_token = create_refresh_token(user_id, db_path=db_path)

    log_audit_event(
        action="LOGIN_SUCCESS",
        resource_type="AUTH",
        actor_id=user_id,
        actor_username=user["username"],
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )

    user_data = {
        "id": user_id,
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "roles": roles,
        "departments": departments,
        "permissions": permissions,
        "is_active": True,
        "is_superuser": bool(user["is_superuser"])
    }

    return user_data, access_token, refresh_token


def refresh_tokens(
    raw_refresh_token: str,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Tuple[str, str]:
    """Rotate refresh token and issue a fresh access token."""
    user_id, new_refresh_token = rotate_refresh_token(raw_refresh_token, db_path=db_path)

    with get_db(db_path) as conn:
        user = conn.execute(
            "SELECT id, username, email, is_active FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user or not user["is_active"]:
            raise PermissionError("User account is inactive or missing.")

    roles = get_user_roles(user_id, db_path=db_path)

    new_access_token = create_access_token(
        user_id=user_id,
        username=user["username"],
        email=user["email"],
        roles=roles
    )

    log_audit_event(
        action="TOKEN_REFRESH",
        resource_type="AUTH",
        actor_id=user_id,
        actor_username=user["username"],
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )

    return new_access_token, new_refresh_token


def logout_user(
    raw_refresh_token: str,
    actor_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Revoke refresh token on logout."""
    revoked = revoke_refresh_token(raw_refresh_token, db_path=db_path)
    log_audit_event(
        action="LOGOUT",
        resource_type="AUTH",
        actor_id=actor_id,
        actor_username=actor_username,
        details={"token_revoked": revoked},
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )
    return revoked


def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """Change user password after verifying current credentials."""
    valid, err_msg = validate_password_strength(new_password)
    if not valid:
        raise ValueError(err_msg)

    with get_db(db_path) as conn:
        user = conn.execute(
            "SELECT id, username, hashed_password FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            raise ValueError("User not found.")

        if not verify_password(current_password, user["hashed_password"]):
            log_audit_event(
                action="PASSWORD_CHANGE_FAILED",
                resource_type="USER",
                actor_id=user_id,
                actor_username=user["username"],
                details={"reason": "Incorrect current password"},
                ip_address=ip_address,
                status="FAILURE",
                db_path=db_path
            )
            raise ValueError("Current password is incorrect.")

        new_hash = hash_password(new_password)
        conn.execute(
            "UPDATE users SET hashed_password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_hash, user_id)
        )
        # Invalidate existing refresh tokens so other sessions must re-authenticate
        conn.execute(
            "UPDATE refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked_at IS NULL",
            (user_id,)
        )
        conn.commit()

    log_audit_event(
        action="PASSWORD_CHANGE_SUCCESS",
        resource_type="USER",
        actor_id=user_id,
        actor_username=user["username"],
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )


def admin_reset_password(
    actor: Dict[str, Any],
    target_user_id: int,
    new_password: str,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    Offline password reset by administrator:
    Sets new password for target user and invalidates all active sessions.
    """
    valid, err_msg = validate_password_strength(new_password)
    if not valid:
        raise ValueError(err_msg)

    with get_db(db_path) as conn:
        target_user = conn.execute(
            "SELECT id, username, is_superuser FROM users WHERE id = ?",
            (target_user_id,)
        ).fetchone()

        if not target_user:
            raise ValueError("Target user not found.")

        # Only SUPER_ADMIN can reset SUPER_ADMIN password
        if target_user["is_superuser"] and not actor.get("is_superuser"):
            raise PermissionError("Only a Super Administrator can reset another Super Administrator's password.")

        new_hash = hash_password(new_password)
        conn.execute(
            """
            UPDATE users
            SET hashed_password = ?, failed_login_attempts = 0, locked_until = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_hash, target_user_id)
        )
        conn.execute(
            "UPDATE refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked_at IS NULL",
            (target_user_id,)
        )
        conn.commit()

    log_audit_event(
        action="ADMIN_PASSWORD_RESET",
        resource_type="USER",
        actor_id=actor["id"],
        actor_username=actor["username"],
        resource_id=str(target_user_id),
        details={"target_username": target_user["username"]},
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )


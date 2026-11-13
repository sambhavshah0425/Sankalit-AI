from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.rag.vector_store import get_db
from app.security.passwords import check_account_lockout
from app.security.rbac import (
    ROLE_SUPER_ADMIN,
    get_user_departments,
    get_user_permissions,
    get_user_roles,
    user_has_permission,
)
from app.security.tokens import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_client_ip(request: Request) -> str:
    """Extract client IP address for security audit records."""
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Authenticate user via Bearer JWT:
    1. Validates and decodes JWT.
    2. Validates user account exists, is active, and is not locked.
    3. Attaches loaded roles, departments, and permissions to user dict.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    with get_db() as conn:
        user_row = conn.execute(
            """
            SELECT id, username, email, full_name, is_active, is_superuser,
                   locked_until, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if not user_row:
            raise credentials_exception

        if not user_row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated."
            )

        is_locked, lock_msg = check_account_lockout(user_row)
        if is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=lock_msg
            )

    roles = get_user_roles(user_id)
    departments = get_user_departments(user_id)
    permissions = get_user_permissions(user_id)

    return {
        "id": user_row["id"],
        "username": user_row["username"],
        "email": user_row["email"],
        "full_name": user_row["full_name"],
        "is_active": bool(user_row["is_active"]),
        "is_superuser": bool(user_row["is_superuser"]),
        "roles": roles,
        "departments": departments,
        "permissions": permissions,
    }


def require_permission(permission_name: str) -> Callable:
    """Enforce fine-grained permission authorization on an endpoint."""
    async def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        if not user_has_permission(
            current_user["roles"],
            current_user["permissions"],
            permission_name
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required permission: '{permission_name}'."
            )
        return current_user

    return permission_checker


def require_role(*required_roles: str) -> Callable:
    """Enforce role membership on an endpoint."""
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        user_roles = current_user.get("roles", [])
        if ROLE_SUPER_ADMIN in user_roles or current_user.get("is_superuser"):
            return current_user

        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(required_roles)}."
            )
        return current_user

    return role_checker


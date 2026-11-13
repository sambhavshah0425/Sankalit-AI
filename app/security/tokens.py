import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import jwt

from app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.rag.vector_store import get_db


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of a raw token string for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: int,
    username: str,
    email: str,
    roles: List[str],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token containing identity and role claims."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    payload = {
        "sub": str(user_id),
        "username": username,
        "email": email,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
        "type": "access"
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Validate and decode a JWT access token.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM]
    )

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token is not an access token.")

    return payload


def create_refresh_token(user_id: int, db_path: Optional[Path] = None) -> str:
    """
    Generate a cryptographically secure random refresh token and persist its SHA-256 hash.
    Returns the raw unhashed token to be delivered to the client.
    """
    raw_token = secrets.token_urlsafe(48)
    token_digest = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
            """,
            (user_id, token_digest, expires_at.isoformat())
        )
        conn.commit()

    return raw_token


def rotate_refresh_token(
    raw_refresh_token: str,
    db_path: Optional[Path] = None
) -> Tuple[int, str]:
    """
    Rotate an existing refresh token:
    1. Validates token hash and expiration.
    2. Revokes current token.
    3. Issues and persists a new refresh token.
    Returns (user_id, new_raw_refresh_token).
    Raises ValueError if token is invalid, expired, or already revoked.
    """
    token_digest = hash_token(raw_refresh_token)
    now = datetime.now(timezone.utc)

    with get_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, user_id, expires_at, revoked_at
            FROM refresh_tokens
            WHERE token_hash = ?
            """,
            (token_digest,)
        ).fetchone()

        if not row:
            raise ValueError("Invalid refresh token.")

        if row["revoked_at"] is not None:
            raise ValueError("Refresh token has already been revoked.")

        expires_at_val = row["expires_at"]
        if isinstance(expires_at_val, str):
            expires_dt = datetime.fromisoformat(expires_at_val)
        else:
            expires_dt = expires_at_val

        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)

        if expires_dt <= now:
            raise ValueError("Refresh token has expired.")

        # Atomically revoke the used refresh token only if it has NOT been revoked yet
        cursor = conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE id = ? AND revoked_at IS NULL
            """,
            (row["id"],)
        )
        if cursor.rowcount == 0:
            raise ValueError("Refresh token has already been revoked or concurrently reused.")

        user_id = row["user_id"]

        # Issue new refresh token
        new_raw_token = secrets.token_urlsafe(48)
        new_digest = hash_token(new_raw_token)
        new_expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
            """,
            (user_id, new_digest, new_expires_at.isoformat())
        )
        conn.commit()

    return user_id, new_raw_token


def revoke_refresh_token(
    raw_refresh_token: str,
    db_path: Optional[Path] = None
) -> bool:
    """Revoke a refresh token on logout. Returns True if token was found and revoked."""
    token_digest = hash_token(raw_refresh_token)
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (token_digest,)
        )
        conn.commit()
        return cursor.rowcount > 0


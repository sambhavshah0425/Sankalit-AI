import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple
import argon2
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.config import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from app.rag.vector_store import get_db

# Initialize Argon2id password hasher tuned for modern security and CPU efficiency
_ph = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    type=argon2.Type.ID
)


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id."""
    if not password:
        raise ValueError("Password cannot be empty.")
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against an Argon2id hash in constant time."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password complexity:
    - Minimum 8 characters
    - At least one letter and at least one digit
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    return True, None


def check_account_lockout(user_row) -> Tuple[bool, Optional[str]]:
    """Check if the user account is temporarily locked due to failed attempts."""
    locked_until_val = user_row["locked_until"]
    if not locked_until_val:
        return False, None

    try:
        if isinstance(locked_until_val, str):
            # Parse ISO or SQLite timestamp
            locked_dt = datetime.fromisoformat(locked_until_val)
        else:
            locked_dt = locked_until_val

        # Ensure tz-aware comparison
        if locked_dt.tzinfo is None:
            locked_dt = locked_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        if locked_dt > now:
            remaining = int((locked_dt - now).total_seconds() // 60) + 1
            return True, f"Account temporarily locked due to failed attempts. Try again in {remaining} minute(s)."
    except Exception:
        pass

    return False, None


def record_failed_login(user_id: int, db_path: Optional[Path] = None) -> None:
    """Increment failed login attempts and lock account if limit reached."""
    with get_db(db_path) as conn:
        user = conn.execute(
            "SELECT failed_login_attempts FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            return

        attempts = user["failed_login_attempts"] + 1
        locked_until = None

        if attempts >= MAX_LOGIN_ATTEMPTS:
            locked_until = (
                datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            ).isoformat()

        conn.execute(
            """
            UPDATE users
            SET failed_login_attempts = ?, locked_until = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (attempts, locked_until, user_id)
        )
        conn.commit()


def reset_failed_logins(user_id: int, db_path: Optional[Path] = None) -> None:
    """Reset failed login attempts counter and clear lockout upon successful login."""
    with get_db(db_path) as conn:
        conn.execute(
            """
            UPDATE users
            SET failed_login_attempts = 0, locked_until = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,)
        )
        conn.commit()


import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.vector_store import get_db

logger = logging.getLogger("audit")

# Sensitive keys to redact from audit metadata
SENSITIVE_KEYS = {
    "password", "hashed_password", "token", "access_token",
    "refresh_token", "secret", "authorization", "raw_token"
}


def sanitize_details(details: Optional[Dict[str, Any]]) -> str:
    """Sanitize detail dictionary to prevent leaking credentials or tokens in audit logs."""
    if not details:
        return "{}"

    safe_dict = {}
    for k, v in details.items():
        if k.lower() in SENSITIVE_KEYS:
            safe_dict[k] = "[REDACTED]"
        elif isinstance(v, dict):
            safe_dict[k] = json.loads(sanitize_details(v))
        else:
            safe_dict[k] = v

    try:
        return json.dumps(safe_dict)
    except Exception:
        return "{}"


def log_audit_event(
    action: str,
    resource_type: str,
    actor_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    status: str = "SUCCESS",
    db_path: Optional[Path] = None
) -> int:
    """
    Persist an immutable security audit entry into the audit_logs table.
    Guarantees no raw passwords or tokens are stored.
    Verifies actor_id exists in users table to prevent foreign key errors if mocked.
    """
    clean_details_str = sanitize_details(details)

    try:
        with get_db(db_path) as conn:
            actual_actor_id = actor_id
            if actual_actor_id is not None:
                exists = conn.execute("SELECT 1 FROM users WHERE id = ?", (actual_actor_id,)).fetchone()
                if not exists:
                    actual_actor_id = None

            cursor = conn.execute(
                """
                INSERT INTO audit_logs (
                    actor_id, actor_username, action, resource_type,
                    resource_id, details, ip_address, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actual_actor_id,
                    actor_username,
                    action,
                    resource_type,
                    str(resource_id) if resource_id is not None else None,
                    clean_details_str,
                    ip_address,
                    status
                )
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as exc:
        logger.error(f"Failed to record audit log: {exc}")
        return -1


def query_audit_logs(
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    actor_id: Optional[int] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieve audit logs for compliance review (accessible to SUPER_ADMIN only)."""
    with get_db(db_path) as conn:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: List[Any] = []

        if action:
            query += " AND action = ?"
            params.append(action)

        if actor_id:
            query += " AND actor_id = ?"
            params.append(actor_id)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

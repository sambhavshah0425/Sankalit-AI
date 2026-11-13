from pathlib import Path
from typing import Any, Dict, List, Optional

from app.rag.vector_store import delete_document, get_db, get_document, list_documents
from app.security.audit import log_audit_event
from app.security.document_access import (
    can_user_manage_document,
    can_user_read_document,
    get_authorized_document_ids,
    get_document_permissions,
    set_document_departments,
)


def get_user_accessible_documents(
    user: Dict[str, Any],
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    project_name: Optional[str] = None,
    document_type: Optional[str] = None,
    classification_status: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieve all document metadata records the user is authorized to access."""
    allowed_ids = get_authorized_document_ids(user, db_path=db_path)
    return list_documents(
        allowed_document_ids=allowed_ids,
        domain_id=domain_id,
        category_id=category_id,
        department_id=department_id,
        project_name=project_name,
        document_type=document_type,
        classification_status=classification_status,
        db_path=db_path
    )


def get_user_accessible_document(
    user: Dict[str, Any],
    document_id: int,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve document metadata by ID if authorized."""
    if not can_user_read_document(user, document_id, db_path=db_path):
        return None
    return get_document(document_id, db_path=db_path)


def delete_user_accessible_document(
    user: Dict[str, Any],
    document_id: int,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Delete document if user has manage/delete privileges."""
    if not can_user_manage_document(user, document_id, db_path=db_path):
        log_audit_event(
            action="DOCUMENT_DELETE_UNAUTHORIZED",
            resource_type="DOCUMENT",
            actor_id=user["id"],
            actor_username=user["username"],
            resource_id=str(document_id),
            ip_address=ip_address,
            status="FAILURE",
            db_path=db_path
        )
        raise PermissionError(f"Unauthorized to delete document {document_id}.")

    doc = get_document(document_id, db_path=db_path)
    filename = doc["filename"] if doc else "unknown"

    deleted = delete_document(document_id, db_path=db_path)
    if deleted:
        log_audit_event(
            action="DOCUMENT_DELETE",
            resource_type="DOCUMENT",
            actor_id=user["id"],
            actor_username=user["username"],
            resource_id=str(document_id),
            details={"filename": filename},
            ip_address=ip_address,
            status="SUCCESS",
            db_path=db_path
        )
    return deleted


def update_document_metadata(
    user: Dict[str, Any],
    document_id: int,
    document_title: Optional[str] = None,
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    project_name: Optional[str] = None,
    project_identifier: Optional[str] = None,
    document_type: Optional[str] = None,
    document_date: Optional[str] = None,
    document_version: Optional[str] = None,
    confidentiality_level: Optional[str] = None,
    visibility: Optional[str] = None,
    department_ids: Optional[List[int]] = None,
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Update document metadata, taxonomy, and visibility if user has management privileges."""
    if not can_user_manage_document(user, document_id, db_path=db_path):
        raise PermissionError(f"Unauthorized to update metadata for document {document_id}.")

    with get_db(db_path) as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found.")

        # Update document fields
        new_title = document_title if document_title is not None else doc["document_title"]
        new_domain = domain_id if domain_id is not None else doc["domain_id"]
        new_cat = category_id if category_id is not None else doc["category_id"]
        new_proj = project_name if project_name is not None else doc["project_name"]
        new_proj_id = project_identifier if project_identifier is not None else doc["project_identifier"]
        new_type = document_type if document_type is not None else doc["document_type"]
        new_date = document_date if document_date is not None else doc["document_date"]
        new_ver = document_version if document_version is not None else doc["document_version"]
        new_conf = confidentiality_level if confidentiality_level is not None else doc["confidentiality_level"]
        new_vis = visibility if visibility is not None else doc["visibility"]

        # Only Super Admin or Admin can set visibility to PUBLIC
        if new_vis == "PUBLIC" and doc["visibility"] != "PUBLIC":
            if not any(r in ("SUPER_ADMIN", "ADMIN") for r in user.get("roles", [])):
                raise PermissionError("Only administrators can set document visibility to PUBLIC.")

        conn.execute(
            """
            UPDATE documents
            SET document_title = ?, domain_id = ?, category_id = ?, project_name = ?,
                project_identifier = ?, document_type = ?, document_date = ?,
                document_version = ?, confidentiality_level = ?, visibility = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                new_title, new_domain, new_cat, new_proj, new_proj_id, new_type,
                new_date, new_ver, new_conf, new_vis, document_id
            )
        )

        if department_ids is not None:
            set_document_departments(document_id, department_ids, db_path=db_path)

        conn.commit()

    log_audit_event(
        action="DOCUMENT_METADATA_UPDATE",
        resource_type="DOCUMENT",
        actor_id=user["id"],
        actor_username=user["username"],
        resource_id=str(document_id),
        details={"title": new_title, "visibility": new_vis, "domain_id": new_domain},
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )

    return get_document(document_id, db_path=db_path) or {}


def update_document_access_permissions(
    user: Dict[str, Any],
    document_id: int,
    permissions_list: List[Dict[str, Any]],
    ip_address: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Update explicit user and role permissions for a document."""
    if not can_user_manage_document(user, document_id, db_path=db_path):
        raise PermissionError(f"Unauthorized to manage permissions for document {document_id}.")

    with get_db(db_path) as conn:
        doc = conn.execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found.")

        # Replace permissions
        conn.execute("DELETE FROM document_permissions WHERE document_id = ?", (document_id,))
        for p in permissions_list:
            u_id = p.get("user_id")
            r_id = p.get("role_id")
            p_type = p.get("permission_type", "read").lower()

            if not u_id and not r_id:
                continue

            conn.execute(
                """
                INSERT INTO document_permissions (document_id, user_id, role_id, permission_type)
                VALUES (?, ?, ?, ?)
                """,
                (document_id, u_id, r_id, p_type)
            )
        conn.commit()

    log_audit_event(
        action="DOCUMENT_PERMISSIONS_UPDATE",
        resource_type="DOCUMENT",
        actor_id=user["id"],
        actor_username=user["username"],
        resource_id=str(document_id),
        details={"permissions": permissions_list},
        ip_address=ip_address,
        status="SUCCESS",
        db_path=db_path
    )

    return get_document_permissions(document_id, db_path=db_path)

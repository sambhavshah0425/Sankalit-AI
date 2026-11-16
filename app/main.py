import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

from app.config import (
    MAX_UPLOAD_SIZE_BYTES,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)
from app.rag.document_loader import SUPPORTED_EXTENSIONS
from app.rag.embedder import EMBEDDING_MODEL, EXPECTED_EMBEDDING_DIM
from app.rag.ingestion import ingest_document
from app.rag.rag_pipeline import answer_query_async, answer_query_stream_async
from app.rag.vector_store import (
    DATABASE_PATH,
    get_database_stats,
    initialize_database,
)
from app.security.audit import log_audit_event, query_audit_logs
from app.security.deps import (
    get_client_ip,
    get_current_user,
    require_permission,
    require_role,
)
from app.security.document_access import (
    VALID_VISIBILITIES,
    can_user_read_document,
    get_authorized_document_ids,
    get_document_permissions,
)
from app.security.rbac import (
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_MANAGER,
)
from app.ai import identity
from app.rag.retriever import retrieve_relevant_chunks
from app.services import (
    auth_service,
    classification_service,
    department_service,
    document_service,
    taxonomy_service,
    user_service,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and filesystem attacks."""
    basename = Path(filename).name
    clean = re.sub(r"[^\w\.-]", "_", basename).strip(" .")
    if not clean:
        clean = "uploaded_document"
    return clean


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and run security migrations
    initialize_database()
    yield


app = FastAPI(
    title="Sankalit Intelligence",
    description="Enterprise Multi-User Local AI Platform for Sankalit Consultant",
    version="0.3.0",
    lifespan=lifespan
)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend_assets")



# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(pattern=EMAIL_REGEX)
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)
    roles: Optional[List[str]] = None
    department_ids: Optional[List[int]] = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class AdminResetPasswordRequest(BaseModel):
    user_id: int
    new_password: str = Field(min_length=8, max_length=128)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(pattern=EMAIL_REGEX)
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None
    roles: Optional[List[str]] = None
    department_ids: Optional[List[int]] = None


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None
    department_ids: Optional[List[int]] = None


class DepartmentCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=20)
    description: Optional[str] = None


class UserDepartmentAssignRequest(BaseModel):
    department_id: int
    is_primary: bool = False


class DocumentPermissionItem(BaseModel):
    user_id: Optional[int] = None
    role_id: Optional[int] = None
    permission_type: str = Field(default="read", pattern="^(read|write|admin)$")


class DocumentPermissionsUpdateRequest(BaseModel):
    permissions: List[DocumentPermissionItem]


class RAGQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Natural language question to ask company knowledge base")
    top_k: int = Field(default=3, ge=1, le=20, description="Maximum number of context chunks to retrieve")
    min_score: float = Field(default=0.25, ge=0.0, le=1.0, description="Minimum cosine similarity threshold")
    detailed: bool = Field(default=False, description="Set to true if full technical retrieval metadata and sources are required")
    domain_id: Optional[int] = None
    domain_slug: Optional[str] = None
    category_id: Optional[int] = None
    department_id: Optional[int] = None
    project_name: Optional[str] = None
    document_type: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "can u list me all 9 question spine?"
            }
        }
    }


class CompanyProfileUpdateRequest(BaseModel):
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    official_website: Optional[str] = None
    contact_information: Optional[str] = None
    additional_information: Optional[Dict[str, Any]] = None


class KnowledgeDomainCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None


class KnowledgeDomainUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class KnowledgeCategoryCreateRequest(BaseModel):
    domain_id: int
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None


class KnowledgeCategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    domain_id: Optional[int] = None
    domain_slug: Optional[str] = None
    category_id: Optional[int] = None
    department_id: Optional[int] = None
    project_name: Optional[str] = None
    document_type: Optional[str] = None
    filename: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.20, ge=0.0, le=1.0)


class ClassificationUpdateRequest(BaseModel):
    domain_id: Optional[int] = None
    category_id: Optional[int] = None
    document_type: Optional[str] = None
    project_name: Optional[str] = None
    project_identifier: Optional[str] = None
    document_title: Optional[str] = None
    status: Optional[str] = None


class DocumentMetadataUpdateRequest(BaseModel):
    document_title: Optional[str] = None
    domain_id: Optional[int] = None
    category_id: Optional[int] = None
    project_name: Optional[str] = None
    project_identifier: Optional[str] = None
    document_type: Optional[str] = None
    document_date: Optional[str] = None
    document_version: Optional[str] = None
    confidentiality_level: Optional[str] = None
    visibility: Optional[str] = None
    department_ids: Optional[List[int]] = None


# =====================================================================
# CORE SYSTEM & HEALTH ENDPOINTS (PRESERVED)
# =====================================================================

@app.get("/")
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    return {
        "application": "Sankalit Intelligence",
        "status": "running"
    }


@app.get("/app")
async def serve_app():
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    raise HTTPException(status_code=404, detail="Frontend build not found.")


@app.get("/brand-icon.svg")
async def serve_brand_icon():
    icon_path = FRONTEND_DIST / "brand-icon.svg"
    if icon_path.exists():
        return FileResponse(str(icon_path))
    raise HTTPException(status_code=404, detail="Brand icon not found.")


@app.get("/sankalit-logo.jpg")
async def serve_sankalit_logo():
    logo_path = FRONTEND_DIST / "sankalit-logo.jpg"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Logo not found.")


@app.get("/sankalit-mark.jpg")
async def serve_sankalit_mark():
    mark_path = FRONTEND_DIST / "sankalit-mark.jpg"
    if mark_path.exists():
        return FileResponse(str(mark_path), media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Mark not found.")


@app.get("/sankalit-logo-lightgrey.png")
async def serve_sankalit_logo_lightgrey():
    logo_path = FRONTEND_DIST / "sankalit-logo-lightgrey.png"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo not found.")


@app.get("/sankalit-logo-white.png")
async def serve_sankalit_logo_white():
    logo_path = FRONTEND_DIST / "sankalit-logo-white.png"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo not found.")


@app.get("/sankalit-logo-charcoal.png")
async def serve_sankalit_logo_charcoal():
    logo_path = FRONTEND_DIST / "sankalit-logo-charcoal.png"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo not found.")


@app.get("/sankalit-logo.png")
async def serve_sankalit_logo_png():
    logo_path = FRONTEND_DIST / "sankalit-logo.png"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo PNG not found.")


@app.get("/favicon.svg")
async def serve_favicon():
    favicon_path = FRONTEND_DIST / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found.")


@app.get("/qa_loader.html")
async def serve_qa_loader():
    loader_path = FRONTEND_DIST / "qa_loader.html"
    if loader_path.exists():
        return FileResponse(str(loader_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="QA Loader not found.")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "application": "Sankalit Intelligence"
    }


@app.get("/health/ollama")
async def ollama_health():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{OLLAMA_BASE_URL}/api/tags"
            )
            response.raise_for_status()

        return {
            "status": "connected",
            "model": OLLAMA_MODEL
        }

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama connection failed: {str(exc)}"
        )


@app.post("/chat")
async def chat(request: ChatRequest):
    """Direct prompt to local Qwen3 model (un-augmented)."""
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": request.message,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": 2048,
                        "num_predict": 256,
                        "temperature": 0.2
                    }
                }
            )

            response.raise_for_status()
            result = response.json()

        return {
            "model": OLLAMA_MODEL,
            "response": result.get("response", ""),
            "done": result.get("done", False)
        }

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI inference failed: {str(exc)}"
        )


# =====================================================================
# AUTHENTICATION ENDPOINTS
# =====================================================================

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, request: Request):
    """
    Register a user account.
    If no users exist in the database, the first user is initialized as SUPER_ADMIN.
    Subsequent self-registrations require ALLOW_OPEN_REGISTRATION to be enabled.
    """
    ip_addr = get_client_ip(request)
    try:
        result = auth_service.register_user(
            username=req.username,
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            requested_roles=req.roles,
            department_ids=req.department_ids,
            actor=None,
            ip_address=ip_addr
        )
        return {
            "message": "User registered successfully.",
            "user": result
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.post("/auth/login")
async def login(request: Request):
    """
    Authenticate user, enforce lockout on consecutive failures, and return JWT tokens.
    Supports both JSON request body and application/x-www-form-urlencoded (Swagger UI OAuth2 Authorize).
    """
    ip_addr = get_client_ip(request)
    username = None
    password = None

    content_type = request.headers.get("content-type", "").lower()
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                username = body.get("username")
                password = body.get("password")
        except Exception:
            pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required."
        )

    try:
        user_data, access_token, refresh_token = auth_service.authenticate_user(
            username_or_email=str(username).strip(),
            password=str(password),
            ip_address=ip_addr
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user_data
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.post("/auth/refresh")
async def refresh_token(req: RefreshRequest, request: Request):
    """Rotate refresh token and issue a fresh access token."""
    ip_addr = get_client_ip(request)
    try:
        new_access_token, new_refresh_token = auth_service.refresh_tokens(
            raw_refresh_token=req.refresh_token,
            ip_address=ip_addr
        )
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.post("/auth/logout")
async def logout(
    req: LogoutRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Revoke user's refresh token."""
    ip_addr = get_client_ip(request)
    revoked = auth_service.logout_user(
        raw_refresh_token=req.refresh_token,
        actor_id=current_user["id"],
        actor_username=current_user["username"],
        ip_address=ip_addr
    )
    return {
        "message": "Logged out successfully.",
        "revoked": revoked
    }


@app.get("/auth/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return authenticated user profile, assigned roles, departments, and effective permissions."""
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "roles": current_user["roles"],
        "departments": current_user["departments"],
        "permissions": sorted(list(current_user["permissions"])),
        "is_active": current_user["is_active"],
        "is_superuser": current_user["is_superuser"]
    }


@app.post("/auth/change-password")
async def change_password_endpoint(
    req: ChangePasswordRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Change current user's password."""
    ip_addr = get_client_ip(request)
    try:
        auth_service.change_password(
            user_id=current_user["id"],
            current_password=req.current_password,
            new_password=req.new_password,
            ip_address=ip_addr
        )
        return {"message": "Password changed successfully. Existing sessions have been invalidated."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post("/auth/reset-password")
async def reset_password_endpoint(
    req: AdminResetPasswordRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("user:update"))
):
    """Administrator-controlled offline password reset."""
    ip_addr = get_client_ip(request)
    try:
        auth_service.admin_reset_password(
            actor=current_user,
            target_user_id=req.user_id,
            new_password=req.new_password,
            ip_address=ip_addr
        )
        return {"message": f"Password for user ID {req.user_id} has been reset."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# =====================================================================
# USER MANAGEMENT ENDPOINTS
# =====================================================================

@app.get("/users")
async def get_users(
    current_user: Dict[str, Any] = Depends(require_permission("user:read"))
):
    """List all registered users."""
    users = user_service.list_users()
    return {"users": users, "total": len(users)}


@app.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user_by_admin(
    req: UserCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("user:create"))
):
    """Administrative user creation."""
    ip_addr = get_client_ip(request)
    try:
        new_user = auth_service.register_user(
            username=req.username,
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            requested_roles=req.roles,
            department_ids=req.department_ids,
            actor=current_user,
            ip_address=ip_addr
        )
        return new_user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user by ID. Users can view their own profile; viewing others requires 'user:read'."""
    if current_user["id"] != user_id and "user:read" not in current_user["permissions"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    u = user_service.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found.")
    return u


@app.patch("/users/{user_id}")
async def update_user_endpoint(
    user_id: int,
    req: UserUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("user:update"))
):
    """Update user attributes, status, roles, or department memberships."""
    ip_addr = get_client_ip(request)
    try:
        updated = user_service.update_user(
            actor=current_user,
            target_user_id=user_id,
            full_name=req.full_name,
            is_active=req.is_active,
            roles=req.roles,
            department_ids=req.department_ids,
            ip_address=ip_addr
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.delete("/users/{user_id}")
async def delete_user_endpoint(
    user_id: int,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("user:delete"))
):
    """Delete a user account."""
    ip_addr = get_client_ip(request)
    try:
        user_service.delete_user(
            actor=current_user,
            target_user_id=user_id,
            ip_address=ip_addr
        )
        return {"deleted": True, "user_id": user_id, "message": "User deleted successfully."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# =====================================================================
# ROLES & PERMISSIONS ENDPOINTS
# =====================================================================

@app.get("/roles")
async def get_roles(
    current_user: Dict[str, Any] = Depends(require_permission("role:read"))
):
    """List all system and custom roles with their permissions."""
    from app.rag.vector_store import get_db
    with get_db() as conn:
        roles = conn.execute("SELECT id, name, description, is_system FROM roles ORDER BY id ASC").fetchall()
        results = []
        for r in roles:
            r_dict = dict(r)
            perms = conn.execute(
                """
                SELECT p.id, p.name, p.description
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                WHERE rp.role_id = ?
                """,
                (r["id"],)
            ).fetchall()
            r_dict["permissions"] = [dict(p) for p in perms]
            results.append(r_dict)
        return {"roles": results}


@app.get("/permissions")
async def get_permissions(
    current_user: Dict[str, Any] = Depends(require_permission("role:read"))
):
    """List all available system permissions."""
    from app.rag.vector_store import get_db
    with get_db() as conn:
        perms = conn.execute("SELECT id, name, description FROM permissions ORDER BY name ASC").fetchall()
        return {"permissions": [dict(p) for p in perms]}


# =====================================================================
# DEPARTMENT ENDPOINTS
# =====================================================================

@app.get("/departments")
async def get_departments(
    current_user: Dict[str, Any] = Depends(require_permission("department:read"))
):
    """List all corporate departments with member counts."""
    depts = department_service.list_departments()
    return {"departments": depts, "total": len(depts)}


@app.post("/departments", status_code=status.HTTP_201_CREATED)
async def create_department_endpoint(
    req: DepartmentCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("department:manage"))
):
    """Create a new department."""
    ip_addr = get_client_ip(request)
    try:
        new_dept = department_service.create_department(
            name=req.name,
            code=req.code,
            description=req.description,
            actor=current_user,
            ip_address=ip_addr
        )
        return new_dept
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post("/users/{user_id}/departments")
async def assign_user_department_endpoint(
    user_id: int,
    req: UserDepartmentAssignRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("department:manage"))
):
    """Assign a user to a department."""
    ip_addr = get_client_ip(request)
    try:
        department_service.assign_user_to_department(
            user_id=user_id,
            department_id=req.department_id,
            is_primary=req.is_primary,
            actor=current_user,
            ip_address=ip_addr
        )
        return {"message": "User assigned to department successfully."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# =====================================================================
# DOCUMENT MANAGEMENT WITH DOCUMENT-LEVEL SECURITY
# =====================================================================

@app.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    visibility: str = Form(default="COMPANY"),
    department_ids: Optional[str] = Form(default=None),
    access_policy: Optional[str] = Form(default=None),
    document_title: Optional[str] = Form(default=None),
    domain_id: Optional[int] = Form(default=None),
    category_id: Optional[int] = Form(default=None),
    project_name: Optional[str] = Form(default=None),
    project_identifier: Optional[str] = Form(default=None),
    document_type: Optional[str] = Form(default=None),
    document_date: Optional[str] = Form(default=None),
    document_version: str = Form(default="1.0"),
    confidentiality_level: str = Form(default="INTERNAL"),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_permission("document:upload"))
):
    """
    Upload document with document-level security & knowledge taxonomy metadata:
    - Enforces 'document:upload' permission.
    - Sets owner_id = authenticated user ID.
    - Sets visibility classification (PUBLIC, COMPANY, DEPARTMENT, RESTRICTED).
    - Sets taxonomy domains, categories, projects, document types, and versions.
    - Associates optional department memberships.
    """
    ip_addr = get_client_ip(request)

    clean_visibility = visibility.strip().upper()
    if clean_visibility not in VALID_VISIBILITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid visibility '{visibility}'. Allowed: {', '.join(sorted(VALID_VISIBILITIES))}."
        )

    parsed_dept_ids: List[int] = []
    if department_ids:
        try:
            parsed_dept_ids = [int(d.strip()) for d in department_ids.split(",") if d.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="department_ids must be a comma-separated list of integers."
            )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename."
        )

    safe_name = sanitize_filename(file.filename)
    file_ext = Path(safe_name).suffix.lower()

    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    destination_path = UPLOADS_DIR / safe_name
    if destination_path.exists():
        stem = destination_path.stem
        counter = 1
        while destination_path.exists():
            destination_path = UPLOADS_DIR / f"{stem}_{counter}{file_ext}"
            counter += 1

    file_size = 0
    try:
        with open(destination_path, "wb") as buffer:
            while chunk := await file.read(1024 * 64):
                file_size += len(chunk)
                if file_size > MAX_UPLOAD_SIZE_BYTES:
                    buffer.close()
                    if destination_path.exists():
                        destination_path.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE if hasattr(status, "HTTP_413_CONTENT_TOO_LARGE") else 413,
                        detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        if destination_path.exists():
            destination_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(exc)}"
        )

    try:
        ingestion_result = ingest_document(
            file_path=str(destination_path),
            owner_id=current_user["id"],
            visibility=clean_visibility,
            access_policy=access_policy,
            department_ids=parsed_dept_ids,
            document_title=document_title,
            domain_id=domain_id,
            category_id=category_id,
            project_name=project_name,
            project_identifier=project_identifier,
            document_type=document_type,
            document_date=document_date,
            document_version=document_version,
            confidentiality_level=confidentiality_level
        )

        log_audit_event(
            action="DOCUMENT_UPLOAD",
            resource_type="DOCUMENT",
            actor_id=current_user["id"],
            actor_username=current_user["username"],
            resource_id=str(ingestion_result["document_id"]),
            details={
                "filename": safe_name,
                "visibility": clean_visibility,
                "departments": parsed_dept_ids,
                "chunks": ingestion_result["total_chunks"]
            },
            ip_address=ip_addr,
            status="SUCCESS"
        )

        return ingestion_result

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Embedding service failure: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {str(exc)}")


@app.get("/documents")
async def get_documents(
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    project_name: Optional[str] = None,
    document_type: Optional[str] = None,
    classification_status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_permission("document:read"))
):
    """
    List indexed documents filtered by authenticated user's access scope and optional metadata criteria.
    Unauthorized documents are excluded from the returned list.
    """
    docs = document_service.get_user_accessible_documents(
        user=current_user,
        domain_id=domain_id,
        category_id=category_id,
        department_id=department_id,
        project_name=project_name,
        document_type=document_type,
        classification_status=classification_status
    )
    return {
        "documents": docs,
        "total_documents": len(docs)
    }


@app.put("/documents/{document_id}")
async def update_document_metadata_endpoint(
    document_id: int,
    req: DocumentMetadataUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("document:upload"))
):
    """Update document metadata, taxonomy, and visibility if user has management privileges."""
    ip_addr = get_client_ip(request)
    try:
        updated = document_service.update_document_metadata(
            user=current_user,
            document_id=document_id,
            document_title=req.document_title,
            domain_id=req.domain_id,
            category_id=req.category_id,
            project_name=req.project_name,
            project_identifier=req.project_identifier,
            document_type=req.document_type,
            document_date=req.document_date,
            document_version=req.document_version,
            confidentiality_level=req.confidentiality_level,
            visibility=req.visibility,
            department_ids=req.department_ids,
            ip_address=ip_addr
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.get("/documents/{document_id}")
async def get_document_by_id(
    document_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("document:read"))
):
    """
    Retrieve document metadata by ID if authorized.
    Returns 404 if document does not exist or user lacks read authorization (prevents ID enumeration).
    """
    doc = document_service.get_user_accessible_document(current_user, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )
    return doc


@app.delete("/documents/{document_id}")
async def delete_document_by_id(
    document_id: int,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("document:delete"))
):
    """
    Delete document and its associated chunks.
    Requires owner, ADMIN, or SUPER_ADMIN authorization.
    """
    ip_addr = get_client_ip(request)
    try:
        deleted = document_service.delete_user_accessible_document(
            user=current_user,
            document_id=document_id,
            ip_address=ip_addr
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found."
            )
        return {
            "deleted": True,
            "document_id": document_id,
            "message": "Document and associated chunks deleted successfully."
        }
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.get("/documents/{document_id}/permissions")
async def get_document_permissions_endpoint(
    document_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("document:manage_permissions"))
):
    """View explicit access permission grants for a document."""
    if not can_user_read_document(current_user, document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} not found.")

    perms = get_document_permissions(document_id)
    return {"document_id": document_id, "permissions": perms}


@app.put("/documents/{document_id}/permissions")
async def update_document_permissions_endpoint(
    document_id: int,
    req: DocumentPermissionsUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("document:manage_permissions"))
):
    """Grant or revoke explicit user/role permissions for a document."""
    ip_addr = get_client_ip(request)
    try:
        perms_list = [p.model_dump() for p in req.permissions]
        updated = document_service.update_document_access_permissions(
            user=current_user,
            document_id=document_id,
            permissions_list=perms_list,
            ip_address=ip_addr
        )
        return {"document_id": document_id, "permissions": updated}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# =====================================================================
# RAG SEMANTIC QUERY WITH DOCUMENT-LEVEL ACCESS ENFORCEMENT
# =====================================================================

@app.post("/rag/query")
async def rag_query(
    request: RAGQueryRequest,
    req: Request,
    current_user: Dict[str, Any] = Depends(require_permission("rag:query"))
):
    """
    CRITICAL WORKFLOW:
    1. Authenticate user.
    2. Compute user's strictly authorized document IDs.
    3. Filter chunks in SQLite so ONLY authorized document chunks are queried.
    4. Compute cosine similarity strictly against authorized chunks.
    5. Generate local answer with cited sources.
    Unauthorized chunks NEVER reach memory, vector calculation, or LLM context!
    """
    ip_addr = get_client_ip(req)

    # Resolve authorized document IDs
    allowed_ids = get_authorized_document_ids(current_user)

    log_audit_event(
        action="RAG_QUERY",
        resource_type="KNOWLEDGE_BASE",
        actor_id=current_user["id"],
        actor_username=current_user["username"],
        details={"query": request.query[:100], "authorized_docs_count": len(allowed_ids)},
        ip_address=ip_addr,
        status="SUCCESS"
    )

    try:
        # Gracefully handle Swagger UI dummy defaults (0, "string", empty)
        effective_domain_id = request.domain_id if request.domain_id and request.domain_id > 0 else None
        effective_category_id = request.category_id if request.category_id and request.category_id > 0 else None
        effective_department_id = request.department_id if request.department_id and request.department_id > 0 else None
        effective_domain_slug = request.domain_slug.strip() if request.domain_slug and request.domain_slug.strip().lower() != "string" else None
        effective_project_name = request.project_name.strip() if request.project_name and request.project_name.strip().lower() != "string" else None
        effective_document_type = request.document_type.strip() if request.document_type and request.document_type.strip().lower() != "string" else None

        result = await answer_query_async(
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
            allowed_document_ids=allowed_ids,
            domain_id=effective_domain_id,
            domain_slug=effective_domain_slug,
            category_id=effective_category_id,
            department_id=effective_department_id,
            project_name=effective_project_name,
            document_type=effective_document_type
        )
        if request.detailed:
            return result
        return {
            "question": request.query,
            "answer": result.get("answer", "")
        }
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RAG inference error: {str(exc)}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(exc)}"
        )


@app.post("/rag/query/stream")
async def rag_query_stream(
    request: RAGQueryRequest,
    req: Request,
    current_user: Dict[str, Any] = Depends(require_permission("rag:query"))
):
    """
    High-performance streaming RAG endpoint via Server-Sent Events (SSE).
    Streams tokens in real-time as they are produced by Ollama to eliminate perceived UI latency.
    """
    ip_addr = get_client_ip(req)
    allowed_ids = get_authorized_document_ids(current_user)

    log_audit_event(
        action="RAG_QUERY_STREAM",
        resource_type="KNOWLEDGE_BASE",
        actor_id=current_user["id"],
        actor_username=current_user["username"],
        details={"query": request.query[:100], "authorized_docs_count": len(allowed_ids)},
        ip_address=ip_addr,
        status="SUCCESS"
    )

    effective_domain_id = request.domain_id if request.domain_id and request.domain_id > 0 else None
    effective_category_id = request.category_id if request.category_id and request.category_id > 0 else None
    effective_department_id = request.department_id if request.department_id and request.department_id > 0 else None
    effective_domain_slug = request.domain_slug.strip() if request.domain_slug and request.domain_slug.strip().lower() != "string" else None
    effective_project_name = request.project_name.strip() if request.project_name and request.project_name.strip().lower() != "string" else None
    effective_document_type = request.document_type.strip() if request.document_type and request.document_type.strip().lower() != "string" else None

    stream_generator = answer_query_stream_async(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
        allowed_document_ids=allowed_ids,
        domain_id=effective_domain_id,
        domain_slug=effective_domain_slug,
        category_id=effective_category_id,
        department_id=effective_department_id,
        project_name=effective_project_name,
        document_type=effective_document_type
    )

    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/rag/stats")
async def rag_stats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return system RAG statistics and model configurations."""
    db_stats = get_database_stats()
    return {
        "total_indexed_documents": db_stats["documents"],
        "total_stored_chunks": db_stats["chunks"],
        "total_registered_users": db_stats["users"],
        "total_departments": db_stats["departments"],
        "database_path": db_stats["database_path"],
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EXPECTED_EMBEDDING_DIM,
        "chat_model": OLLAMA_MODEL
    }


# =====================================================================
# COMPANY PROFILE & IDENTITY ENDPOINTS
# =====================================================================

@app.get("/company/profile")
async def get_company_profile_endpoint():
    """Retrieve official company profile and organizational capabilities."""
    return identity.get_company_profile()


@app.put("/company/profile")
async def update_company_profile_endpoint(
    req: CompanyProfileUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_permission("company_profile:update"))
):
    """Update official company profile record."""
    try:
        profile = taxonomy_service.update_company_profile(
            company_name=req.company_name,
            company_description=req.company_description,
            mission=req.mission,
            vision=req.vision,
            official_website=req.official_website,
            contact_information=req.contact_information,
            additional_information=req.additional_information,
            actor=current_user
        )
        return profile
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# =====================================================================
# KNOWLEDGE TAXONOMY (DOMAINS & CATEGORIES)
# =====================================================================

@app.get("/knowledge/domains")
async def get_knowledge_domains(
    include_inactive: bool = False,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:read"))
):
    """List knowledge domains with category and document counts."""
    domains = taxonomy_service.list_knowledge_domains(include_inactive=include_inactive)
    return {"domains": domains, "total": len(domains)}


@app.get("/knowledge/domains/{domain_id}")
async def get_knowledge_domain_by_id(
    domain_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:read"))
):
    """Retrieve domain details by ID."""
    domain = taxonomy_service.get_knowledge_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Domain {domain_id} not found.")
    return domain


@app.post("/knowledge/domains", status_code=status.HTTP_201_CREATED)
async def create_knowledge_domain_endpoint(
    req: KnowledgeDomainCreateRequest,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:manage"))
):
    """Create a new knowledge domain."""
    try:
        created = taxonomy_service.create_knowledge_domain(
            name=req.name,
            slug=req.slug,
            description=req.description,
            actor=current_user
        )
        return created
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.put("/knowledge/domains/{domain_id}")
async def update_knowledge_domain_endpoint(
    domain_id: int,
    req: KnowledgeDomainUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:manage"))
):
    """Update domain attributes."""
    try:
        updated = taxonomy_service.update_knowledge_domain(
            domain_id=domain_id,
            name=req.name,
            slug=req.slug,
            description=req.description,
            is_active=req.is_active,
            actor=current_user
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.delete("/knowledge/domains/{domain_id}")
async def deactivate_knowledge_domain_endpoint(
    domain_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:manage"))
):
    """Deactivate knowledge domain."""
    try:
        success = taxonomy_service.deactivate_knowledge_domain(domain_id, actor=current_user)
        return {"deactivated": success, "domain_id": domain_id}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get("/knowledge/categories")
async def get_knowledge_categories(
    domain_id: Optional[int] = None,
    include_inactive: bool = False,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:read"))
):
    """List knowledge categories optionally filtered by domain_id."""
    cats = taxonomy_service.list_knowledge_categories(domain_id=domain_id, include_inactive=include_inactive)
    return {"categories": cats, "total": len(cats)}


@app.get("/knowledge/domains/{domain_id}/categories")
async def get_categories_for_domain(
    domain_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:read"))
):
    """Retrieve all categories belonging to a specific domain."""
    cats = taxonomy_service.list_knowledge_categories(domain_id=domain_id, include_inactive=False)
    return {"domain_id": domain_id, "categories": cats, "total": len(cats)}


@app.post("/knowledge/categories", status_code=status.HTTP_201_CREATED)
async def create_knowledge_category_endpoint(
    req: KnowledgeCategoryCreateRequest,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:manage"))
):
    """Create a new knowledge category within a domain."""
    try:
        created = taxonomy_service.create_knowledge_category(
            domain_id=req.domain_id,
            name=req.name,
            slug=req.slug,
            description=req.description,
            actor=current_user
        )
        return created
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.put("/knowledge/categories/{category_id}")
async def update_knowledge_category_endpoint(
    category_id: int,
    req: KnowledgeCategoryUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:manage"))
):
    """Update a knowledge category."""
    try:
        updated = taxonomy_service.update_knowledge_category(
            category_id=category_id,
            name=req.name,
            slug=req.slug,
            description=req.description,
            is_active=req.is_active,
            actor=current_user
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.delete("/knowledge/categories/{category_id}")
async def deactivate_knowledge_category_endpoint(
    category_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("taxonomy:manage"))
):
    """Deactivate a knowledge category."""
    try:
        success = taxonomy_service.deactivate_knowledge_category(category_id, actor=current_user)
        return {"deactivated": success, "category_id": category_id}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# =====================================================================
# DOMAIN-AWARE KNOWLEDGE SEARCH
# =====================================================================

@app.post("/knowledge/search")
async def search_knowledge(
    req: KnowledgeSearchRequest,
    current_user: Dict[str, Any] = Depends(require_permission("document:read"))
):
    """
    Perform authorized multi-mode semantic search against the company knowledge base.
    Applies user document authorization at the SQL layer, followed by domain/metadata filters.
    """
    allowed_ids = get_authorized_document_ids(current_user)
    results = retrieve_relevant_chunks(
        query=req.query,
        top_k=req.top_k,
        min_score=req.min_score,
        allowed_document_ids=allowed_ids,
        domain_id=req.domain_id,
        domain_slug=req.domain_slug,
        category_id=req.category_id,
        department_id=req.department_id,
        project_name=req.project_name,
        document_type=req.document_type,
        filename=req.filename
    )
    return {
        "query": req.query,
        "results": results,
        "total_results": len(results)
    }


# =====================================================================
# CLASSIFICATION MANAGEMENT
# =====================================================================

@app.get("/knowledge/classification/pending")
async def get_pending_classifications_endpoint(
    limit: int = 50,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_permission("classification:manage"))
):
    """List documents awaiting classification review (NEEDS_REVIEW or UNCLASSIFIED)."""
    pending = classification_service.get_pending_classifications(limit=limit, offset=offset)
    return {"pending": pending, "total": len(pending)}


@app.get("/knowledge/classification/{document_id}")
async def get_document_classification_endpoint(
    document_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("classification:manage"))
):
    """Retrieve classification details for a document."""
    doc = document_service.get_user_accessible_document(current_user, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} not found.")
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "document_title": doc.get("document_title"),
        "domain_id": doc.get("domain_id"),
        "domain_name": doc.get("domain_name"),
        "domain_slug": doc.get("domain_slug"),
        "category_id": doc.get("category_id"),
        "category_name": doc.get("category_name"),
        "category_slug": doc.get("category_slug"),
        "document_type": doc.get("document_type"),
        "project_name": doc.get("project_name"),
        "classification_status": doc.get("classification_status"),
        "classification_confidence": doc.get("classification_confidence"),
        "classification_explanation": doc.get("classification_explanation")
    }


@app.put("/knowledge/classification/{document_id}")
async def update_classification_endpoint(
    document_id: int,
    req: ClassificationUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_permission("classification:manage"))
):
    """Manually update or correct classification for a document."""
    try:
        updated = classification_service.update_document_classification(
            document_id=document_id,
            domain_id=req.domain_id,
            category_id=req.category_id,
            document_type=req.document_type,
            project_name=req.project_name,
            project_identifier=req.project_identifier,
            document_title=req.document_title,
            status=req.status,
            actor=current_user
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.post("/knowledge/classification/{document_id}/approve")
async def approve_classification_endpoint(
    document_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("classification:manage"))
):
    """Approve suggested classification, transitioning status to CLASSIFIED."""
    try:
        approved = classification_service.approve_document_classification(document_id, actor=current_user)
        return approved
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.post("/knowledge/classification/{document_id}/reclassify")
async def reclassify_document_endpoint(
    document_id: int,
    current_user: Dict[str, Any] = Depends(require_permission("classification:manage"))
):
    """Trigger re-analysis and classification of document content."""
    doc = document_service.get_user_accessible_document(current_user, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} not found.")

    from app.rag.vector_store import get_document_chunks
    chunks = get_document_chunks(document_id)
    combined_sample = " ".join(c["text"] for c in chunks[:5])
    new_class = classification_service.classify_document_content(combined_sample, doc["filename"])

    updated = classification_service.update_document_classification(
        document_id=document_id,
        domain_id=new_class.get("domain_id"),
        category_id=new_class.get("category_id"),
        document_type=new_class.get("document_type"),
        project_name=new_class.get("project_name"),
        status=new_class.get("status"),
        actor=current_user
    )
    return updated


# =====================================================================
# KNOWLEDGE STATISTICS (RESPECTING CALLER AUTHORIZATION)
# =====================================================================

@app.get("/knowledge/stats")
async def get_knowledge_statistics_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Return knowledge base statistics strictly scoped to the calling user's authorized documents.
    Prevents metadata leakage for restricted departmental resources.
    """
    allowed_ids = get_authorized_document_ids(current_user)
    stats = taxonomy_service.get_taxonomy_statistics(allowed_document_ids=allowed_ids)
    return stats


@app.get("/knowledge/domains/{domain_id}/stats")
async def get_domain_statistics_endpoint(
    domain_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve statistics for a specific domain within the caller's authorized scope."""
    domain = taxonomy_service.get_knowledge_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Domain {domain_id} not found.")

    allowed_ids = get_authorized_document_ids(current_user)
    stats = taxonomy_service.get_taxonomy_statistics(allowed_document_ids=allowed_ids)
    domain_stat = next(
        (d for d in stats["documents_by_domain"] if d["domain_slug"] == domain["slug"]),
        {"domain_name": domain["name"], "domain_slug": domain["slug"], "count": 0}
    )
    return {"domain": domain, "statistics": domain_stat}


# =====================================================================
# AUDIT LOGS ENDPOINT (SUPER_ADMIN ONLY)
# =====================================================================

@app.get("/audit/logs")
async def get_audit_logs(
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_permission("audit:read"))
):
    """View security and compliance audit logs."""
    logs = query_audit_logs(limit=limit, offset=offset, action=action)
    return {"logs": logs, "count": len(logs)}

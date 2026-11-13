# Sankalit Intelligence — Comprehensive API Reference

**Base URL:** `http://localhost:8000`  
**Authentication Scheme:** HTTP Bearer (`Authorization: Bearer <access_token>`)  

---

## 1. System & Health Endpoints (Public)

### 1.1 Root Status
- **Method:** `GET`
- **Path:** `/`
- **Auth:** None
- **Response:** `200 OK`
```json
{
  "application": "Sankalit Intelligence",
  "status": "running"
}
```

### 1.2 Health Check
- **Method:** `GET`
- **Path:** `/health`
- **Auth:** None
- **Response:** `200 OK`
```json
{
  "status": "healthy",
  "application": "Sankalit Intelligence"
}
```

### 1.3 Ollama Connection Health
- **Method:** `GET`
- **Path:** `/health/ollama`
- **Auth:** None
- **Response:** `200 OK`
```json
{
  "status": "connected",
  "model": "qwen3:1.7b"
}
```

---

## 2. Authentication & Profile Endpoints

### 2.1 User Registration / Bootstrap
- **Method:** `POST`
- **Path:** `/auth/register`
- **Auth:** Public for first user (bootstrap Super Admin); requires `user:create` permission for subsequent users.
- **Request Body:**
```json
{
  "username": "superadmin",
  "email": "superadmin@sankalit.com",
  "password": "SuperSecurePassword123!",
  "full_name": "Executive Admin",
  "roles": ["SUPER_ADMIN"],
  "department_ids": [7]
}
```
- **Response:** `201 Created`

### 2.2 User Login
- **Method:** `POST`
- **Path:** `/auth/login`
- **Auth:** None
- **Request Body:**
```json
{
  "username_or_email": "superadmin@sankalit.com",
  "password": "SuperSecurePassword123!"
}
```
- **Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "bearer",
  "refresh_token": "v07vD8...random_crypto_string...",
  "user": {
    "id": 1,
    "username": "superadmin",
    "email": "superadmin@sankalit.com",
    "full_name": "Executive Admin",
    "roles": ["SUPER_ADMIN"],
    "departments": [{"id": 7, "name": "Management", "code": "MGMT"}],
    "permissions": ["user:create", "user:read", "document:upload", "..."],
    "is_active": true,
    "is_superuser": true
  }
}
```

### 2.3 Token Refresh Rotation
- **Method:** `POST`
- **Path:** `/auth/refresh`
- **Auth:** None (presents refresh token)
- **Request Body:**
```json
{
  "refresh_token": "v07vD8...active_refresh_token..."
}
```
- **Response:** `200 OK` (returns fresh access token and rotated refresh token)

### 2.4 User Logout
- **Method:** `POST`
- **Path:** `/auth/logout`
- **Auth:** Bearer Token
- **Request Body:**
```json
{
  "refresh_token": "v07vD8...active_refresh_token..."
}
```
- **Response:** `200 OK`

### 2.5 Current User Profile
- **Method:** `GET`
- **Path:** `/auth/me`
- **Auth:** Bearer Token
- **Response:** `200 OK` (returns caller profile, roles, departments, and resolved permissions)

### 2.6 Change Password
- **Method:** `POST`
- **Path:** `/auth/change-password`
- **Auth:** Bearer Token
- **Request Body:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewSecurePassword456!"
}
```
- **Response:** `200 OK`

### 2.7 Offline Administrator Password Reset
- **Method:** `POST`
- **Path:** `/auth/reset-password`
- **Auth:** Bearer Token (requires `user:update` permission)
- **Request Body:**
```json
{
  "user_id": 2,
  "new_password": "TemporaryPassword789!"
}
```
- **Response:** `200 OK`

---

## 3. User & Department Management Endpoints

### 3.1 List Users
- **Method:** `GET`
- **Path:** `/users`
- **Auth:** Bearer Token (requires `user:read` permission)
- **Response:** `200 OK` (list of user objects with department and role metadata)

### 3.2 Create User
- **Method:** `POST`
- **Path:** `/users`
- **Auth:** Bearer Token (requires `user:create` permission)
- **Request Body:**
```json
{
  "username": "hr_lead",
  "email": "hr_lead@sankalit.com",
  "password": "HrSecurePassword123!",
  "full_name": "Priya Sharma",
  "roles": ["EMPLOYEE"],
  "department_ids": [1]
}
```
- **Response:** `201 Created`

### 3.3 Update User
- **Method:** `PUT`
- **Path:** `/users/{user_id}`
- **Auth:** Bearer Token (requires `user:update` permission)

### 3.4 Delete User
- **Method:** `DELETE`
- **Path:** `/users/{user_id}`
- **Auth:** Bearer Token (requires `user:delete` permission)

### 3.5 List Departments
- **Method:** `GET`
- **Path:** `/departments`
- **Auth:** Bearer Token (requires `department:read` permission)

### 3.6 Create Department
- **Method:** `POST`
- **Path:** `/departments`
- **Auth:** Bearer Token (requires `department:manage` permission)

---

## 4. Secure Document Management Endpoints

### 4.1 Ingest Document
- **Method:** `POST`
- **Path:** `/documents/upload`
- **Auth:** Bearer Token (requires `document:upload` permission)
- **Form Data:**
  - `file`: PDF or DOCX file binary.
  - `visibility`: `"PUBLIC" | "COMPANY" | "DEPARTMENT" | "RESTRICTED"` (default: `"COMPANY"`).
  - `access_policy`: `"DEFAULT" | "DEPARTMENT_ONLY" | "OWNER_ONLY" | "EXPLICIT_GRANTS"`.
  - `department_ids`: Comma-separated list of department IDs (e.g. `"1,2"`).
- **Response:** `200 OK`
```json
{
  "document_id": 1,
  "filename": "Sankalit_HR_Compensation_2026.pdf",
  "file_type": ".pdf",
  "content_hash": "c6218995a9732b1...",
  "character_count": 294,
  "total_chunks": 1,
  "embedded_chunks": 1,
  "ingestion_status": "success",
  "duplicate_status": "new",
  "visibility": "DEPARTMENT",
  "departments": [{"id": 1, "name": "HR", "code": "HR"}]
}
```

### 4.2 List Accessible Documents
- **Method:** `GET`
- **Path:** `/documents`
- **Auth:** Bearer Token (requires `document:read` permission)
- **Description:** Returns only documents authorized to the calling user based on roles, ownership, and department memberships.
- **Response:** `200 OK`

### 4.3 Get Document Details
- **Method:** `GET`
- **Path:** `/documents/{document_id}`
- **Auth:** Bearer Token (requires `document:read` permission + document authorization check)
- **Response:** `200 OK`

### 4.4 Delete Document
- **Method:** `DELETE`
- **Path:** `/documents/{document_id}`
- **Auth:** Bearer Token (Caller must be document owner or possess `document:delete_any` permission)
- **Response:** `200 OK`

### 4.5 Grant Document Permission
- **Method:** `POST`
- **Path:** `/documents/{document_id}/permissions`
- **Auth:** Bearer Token (requires `document:grant` permission)
- **Request Body:**
```json
{
  "user_id": 5,
  "permission_type": "read"
}
```
- **Response:** `201 Created`

---

## 5. Secure Semantic RAG Query Endpoint

### 5.1 Query Knowledge Base
- **Method:** `POST`
- **Path:** `/rag/query`
- **Auth:** Bearer Token (requires `rag:query` permission)
- **Request Body:**
```json
{
  "query": "What is the annual retention bonus percentage for HR staff?",
  "top_k": 3,
  "min_score": 0.25
}
```
- **Response (Authorized User):** `200 OK`
```json
{
  "query": "What is the annual retention bonus percentage for HR staff?",
  "answer": "The annual retention bonus percentage for HR staff is 28 percent, as stated in the document: [Source: Sankalit_HR_Compensation_2026.pdf, Chunk 0].",
  "sources": [
    {
      "filename": "Sankalit_HR_Compensation_2026.pdf",
      "chunk_index": 0,
      "similarity": 0.7473
    }
  ],
  "retrieval_status": "success",
  "model": "qwen3:1.7b"
}
```
- **Response (Unauthorized User):** `200 OK`
```json
{
  "query": "What is the annual retention bonus percentage for HR staff?",
  "answer": "The available documents do not contain enough information to answer this question.",
  "sources": [],
  "retrieval_status": "insufficient_context",
  "model": "qwen3:1.7b"
}
```

---

## 6. Audit Logging Endpoints

### 6.1 Query Security Audit Logs
- **Method:** `GET`
- **Path:** `/audit/logs`
- **Auth:** Bearer Token (requires `audit:read` permission; Super Admin only)
- **Query Parameters:**
  - `action`: Filter by action (e.g. `LOGIN_FAILED`, `DOCUMENT_UPLOAD`, `RAG_QUERY`).
  - `limit`: Number of records (default: 50, max: 200).
  - `offset`: Pagination offset.
- **Response:** `200 OK`
```json
[
  {
    "id": 14,
    "created_at": "2026-11-13 10:01:00",
    "actor_id": 1,
    "actor_username": "hr_lead",
    "action": "DOCUMENT_UPLOAD",
    "resource_type": "document",
    "resource_id": "1",
    "details": {
      "filename": "Sankalit_HR_Compensation_2026.pdf",
      "visibility": "DEPARTMENT"
    },
    "ip_address": "127.0.0.1",
    "status": "SUCCESS"
  }
]
```

---

## 7. Company Profile & Identity Endpoints

### 7.1 Get Official Company Profile
- **Method:** `GET`
- **Path:** `/company/profile`
- **Auth:** Public
- **Response:** `200 OK`
```json
{
  "company_name": "Sankalit Consultant",
  "company_description": "Sankalit Consultant is a multidisciplinary engineering and consulting consultancy firm specializing in Acoustics, Audio-Visual Systems, Airport Systems, Architectural Lighting, Mechanical, Electrical, Plumbing (MEP), and Information Technology infrastructure design.",
  "mission": "Delivering state-of-the-art engineering consultancy and intelligent infrastructure design with precision, innovation, and technological excellence.",
  "vision": "To be a premier multidisciplinary engineering consultancy recognized globally for transformative infrastructure, technological integration, and sustainable design.",
  "official_website": "https://sankalit.com",
  "contact_information": "info@sankalit.com",
  "practice_areas": [
    "Acoustics & Audio-Visual",
    "Airport Systems & Technology",
    "Information Technology & Networking",
    "Architectural Lighting Design",
    "MEP (Mechanical, Electrical, Plumbing, Fire Life Safety)",
    "Executive Management & Operations"
  ]
}
```

### 7.2 Update Company Profile
- **Method:** `PUT`
- **Path:** `/company/profile`
- **Auth:** Bearer Token (requires `company_profile:update` permission; Super Admin / Admin)
- **Request Body:**
```json
{
  "mission": "Updated corporate mission statement.",
  "vision": "Updated vision statement.",
  "official_website": "https://sankalit.com",
  "contact_information": "contact@sankalit.com"
}
```
- **Response:** `200 OK` (returns updated company profile)

---

## 8. Knowledge Taxonomy Endpoints (Domains & Categories)

### 8.1 List Knowledge Domains
- **Method:** `GET`
- **Path:** `/knowledge/domains?include_inactive=false`
- **Auth:** Bearer Token (requires `taxonomy:read` permission)
- **Response:** `200 OK`
```json
{
  "domains": [
    {
      "id": 1,
      "name": "Company Profile",
      "slug": "company-profile",
      "description": "Company overview, history, mission, vision, and core capabilities",
      "is_active": 1,
      "category_count": 5,
      "document_count": 2
    },
    {
      "id": 2,
      "name": "Acoustic",
      "slug": "acoustic",
      "description": "Architectural acoustics, noise & vibration control, sound isolation, and auditorium design",
      "is_active": 1,
      "category_count": 6,
      "document_count": 4
    }
  ],
  "total": 10
}
```

### 8.2 Create Knowledge Domain
- **Method:** `POST`
- **Path:** `/knowledge/domains`
- **Auth:** Bearer Token (requires `taxonomy:manage` permission)
- **Request Body:**
```json
{
  "name": "Sustainable Architecture",
  "slug": "sustainable-architecture",
  "description": "Green building certification, LEED compliance, and energy modeling"
}
```
- **Response:** `201 Created`

### 8.3 Update Knowledge Domain
- **Method:** `PUT`
- **Path:** `/knowledge/domains/{domain_id}`
- **Auth:** Bearer Token (requires `taxonomy:manage` permission)
- **Request Body:**
```json
{
  "description": "Updated domain description.",
  "is_active": true
}
```
- **Response:** `200 OK`

### 8.4 Deactivate Knowledge Domain
- **Method:** `DELETE`
- **Path:** `/knowledge/domains/{domain_id}`
- **Auth:** Bearer Token (requires `taxonomy:manage` permission)
- **Response:** `200 OK`
```json
{
  "deactivated": true,
  "domain_id": 11
}
```

### 8.5 List Categories
- **Method:** `GET`
- **Path:** `/knowledge/categories?domain_id=2`
- **Auth:** Bearer Token (requires `taxonomy:read` permission)
- **Response:** `200 OK`

### 8.6 Create Category
- **Method:** `POST`
- **Path:** `/knowledge/categories`
- **Auth:** Bearer Token (requires `taxonomy:manage` permission)
- **Request Body:**
```json
{
  "domain_id": 2,
  "name": "Studio Acoustics",
  "slug": "studio-acoustics",
  "description": "Recording studio and broadcast acoustic isolation"
}
```
- **Response:** `201 Created`

### 8.7 Update Category
- **Method:** `PUT`
- **Path:** `/knowledge/categories/{category_id}`
- **Auth:** Bearer Token (requires `taxonomy:manage` permission)

### 8.8 Deactivate Category
- **Method:** `DELETE`
- **Path:** `/knowledge/categories/{category_id}`
- **Auth:** Bearer Token (requires `taxonomy:manage` permission)

---

## 9. Domain-Aware Knowledge Search & Enhanced RAG

### 9.1 Multi-Mode Knowledge Search
- **Method:** `POST`
- **Path:** `/knowledge/search`
- **Auth:** Bearer Token (requires `document:read` permission)
- **Request Body:**
```json
{
  "query": "auditorium reverberation time",
  "domain_id": 2,
  "category_id": null,
  "project_name": null,
  "document_type": "specification",
  "search_mode": "hybrid",
  "top_k": 5
}
```
- **Response:** `200 OK`
```json
{
  "query": "auditorium reverberation time",
  "search_mode": "hybrid",
  "domain_id": 2,
  "results": [
    {
      "chunk_id": 14,
      "document_id": 3,
      "filename": "Auditorium_Acoustics_Spec.pdf",
      "document_title": "Auditorium Acoustic Engineering Guide",
      "chunk_index": 2,
      "text": "The RT60 reverberation time target for the hall is 1.4 seconds...",
      "similarity": 0.8842,
      "document_type": "specification"
    }
  ],
  "total": 1
}
```

### 9.2 Enhanced Domain-Aware RAG Query
- **Method:** `POST`
- **Path:** `/rag/query`
- **Auth:** Bearer Token (requires `rag:query` permission)
- **Request Body:**
```json
{
  "query": "What are our RT60 standards for multi-purpose halls?",
  "domain_id": 2,
  "project_name": null,
  "document_type": "specification",
  "top_k": 5,
  "min_score": 0.35
}
```
- **Response:** `200 OK`
```json
{
  "query": "What are our RT60 standards for multi-purpose halls?",
  "answer": "According to Sankalit engineering standards, multi-purpose halls should maintain an RT60 reverberation time between 1.4 and 1.6 seconds [Source: Auditorium_Acoustics_Spec.pdf, Chunk 2].",
  "classification": "DEPARTMENT_SPECIFIC",
  "detected_domain": "acoustic",
  "sources": [
    {
      "filename": "Auditorium_Acoustics_Spec.pdf",
      "chunk_index": 2,
      "similarity": 0.8842,
      "document_title": "Auditorium Acoustic Engineering Guide",
      "domain_slug": "acoustic"
    }
  ],
  "citations": [
    {
      "filename": "Auditorium_Acoustics_Spec.pdf",
      "chunk_index": 2,
      "status": "VERIFIED_EXACT"
    }
  ],
  "unverified_citations": [],
  "has_valid_citations": true,
  "retrieval_status": "success",
  "model": "qwen3:1.7b"
}
```

---

## 10. Document Classification & Metadata Management

### 10.1 Pending Classification Queue
- **Method:** `GET`
- **Path:** `/knowledge/classification/pending`
- **Auth:** Bearer Token (requires `classification:manage` permission)
- **Response:** `200 OK` (list of documents needing review)

### 10.2 Review Document Classification
- **Method:** `GET`
- **Path:** `/knowledge/classification/{document_id}`
- **Auth:** Bearer Token (requires `classification:manage` permission)

### 10.3 Update Document Classification
- **Method:** `PUT`
- **Path:** `/knowledge/classification/{document_id}`
- **Auth:** Bearer Token (requires `classification:manage` permission)
- **Request Body:**
```json
{
  "domain_id": 3,
  "category_id": 7,
  "project_name": "Delhi Airport Terminal 3",
  "document_type": "specification",
  "status": "CLASSIFIED",
  "explanation": "Manually verified as Delhi Airport baggage handling technical spec."
}
```

### 10.4 Approve Classification
- **Method:** `POST`
- **Path:** `/knowledge/classification/{document_id}/approve`
- **Auth:** Bearer Token (requires `classification:manage` permission)

### 10.5 Trigger Reclassification
- **Method:** `POST`
- **Path:** `/knowledge/classification/{document_id}/reclassify`
- **Auth:** Bearer Token (requires `classification:manage` permission)

### 10.6 Knowledge Statistics
- **Method:** `GET`
- **Path:** `/knowledge/stats`
- **Auth:** Bearer Token (requires `taxonomy:read` permission)
- **Response:** `200 OK` (returns counts of domains, categories, classified docs, pending docs, chunk statistics)

### 10.7 Update Document Metadata
- **Method:** `PUT`
- **Path:** `/documents/{document_id}`
- **Auth:** Bearer Token (requires `document:read`, and user must be owner or Admin/Manager)
- **Request Body:**
```json
{
  "document_title": "Project Horizon Acoustical DBR Final",
  "domain_id": 2,
  "category_id": 4,
  "project_name": "Project Horizon",
  "project_identifier": "PH-2026-01",
  "document_type": "report",
  "confidentiality_level": "CONFIDENTIAL",
  "visibility": "DEPARTMENT"
}
```
*(Note: Setting visibility to `PUBLIC` strictly requires Super Admin or Admin role).*


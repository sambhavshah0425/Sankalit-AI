# Sankalit Intelligence — Security Architecture & RBAC Specification

## Milestone 2: Multi-User Identity, RBAC, and Document-Level Security

**Document Version:** 2.0  
**Target Environment:** Local On-Premises / Offline (Windows 11, Intel Core i5-1235U, ~8 GB RAM)  
**Database:** SQLite 3 (`data/sankalit.db`)  
**Inference Engine:** Local Ollama (`qwen3:1.7b`, `nomic-embed-text`)  

---

## 1. Architectural Philosophy & Zero-Trust Local Design

Sankalit Intelligence is designed as an entirely local, air-gapped enterprise intelligence platform. While traditional cloud architectures offload authentication and authorization to external OAuth/IAM providers or cloud vector databases, Sankalit Intelligence enforces strict zero-trust security locally within the application and database layer.

Key Tenets:
1. **Never Trust Prompts for Authorization**: LLM prompt boundaries cannot enforce security. Access control is enforced deterministically at the SQL query layer before any vector calculations or LLM context construction occur.
2. **Zero Information Leakage in RAG**: If a user is not permitted to read a document, that document's chunks are never loaded into memory, never evaluated for cosine similarity, and never included in the prompt context.
3. **Defense in Depth**: Every API request is verified across three independent layers:
   - Layer 1: Identity & Token Validation (JWT signature, expiration, active account check, lockout verification).
   - Layer 2: Functional RBAC Permission Verification (Endpoint operation rights such as `user:create` or `document:upload`).
   - Layer 3: Data-Level Row Filtering (SQL-level query constraints based on ownership, department membership, and visibility).

---

## 2. Authentication Architecture

```
User Login Request (email/username, password)
    ↓
Rate Limiter / Brute-Force Check (Check consecutive failures & lockout timestamp)
    ↓
Argon2id Hash Verification (time_cost=2, memory_cost=64MB, parallelism=1)
    ↓ Success
Reset Failed Counter
    ↓
Generate JWT Access Token (HS256, 30 min lifetime) + Cryptographic Refresh Token (Hashed SHA-256 in DB, 7-day lifetime)
    ↓
Log Structured Audit Event (Actor, Action, Resource, Status, Client IP)
```

### 2.1 Password Hashing: Argon2id
- **Algorithm**: Argon2id via `argon2-cffi`.
- **Parameters**: `time_cost=2`, `memory_cost=65536` (64 MB RAM), `parallelism=1`.
- **Policy Enforcement**:
  - Minimum 8 characters.
  - At least 1 uppercase letter (`A-Z`).
  - At least 1 lowercase letter (`a-z`).
  - At least 1 digit (`0-9`).
  - At least 1 special character (`!@#$%^&*...`).
- Plaintext passwords are never persisted and never included in audit logs.

### 2.2 Brute-Force & Credential Stuffing Protection
- **Failure Tracking**: Tracks consecutive failed login attempts per account in `users.failed_login_attempts`.
- **Threshold**: After 5 consecutive failed attempts, the account is automatically locked for 15 minutes (`users.locked_until`).
- **Offline Administrative Reset**: Super Administrators can clear lockouts and reset user passwords directly via administrative endpoints without requiring email/internet infrastructure.

### 2.3 Token Lifecycle & Refresh Rotation
- **Access Tokens**: Short-lived JWT (30 minutes) carrying claims: `sub` (user_id), `username`, `email`, `roles`, `iat`, `exp`.
- **Refresh Tokens**: Cryptographically random 32-byte URL-safe string. Stored as a one-way SHA-256 hash in `refresh_tokens`.
- **Rotation**: On every token refresh, the old refresh token is marked as revoked, and a brand new refresh token is issued.
- **Replay Detection**: If a revoked refresh token is presented, the request is rejected with `401 Unauthorized`.
- **Logout**: Immediate revocation of the active refresh token.

---

## 3. Role-Based Access Control (RBAC)

Permissions are decoupled from roles to provide granular capability enforcement. Roles represent functional archetypes that aggregate fine-grained permissions.

### 3.1 Initial Roles & Capability Matrix

| Permission | SUPER_ADMIN | ADMIN | MANAGER | EMPLOYEE | VIEWER | Description |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `user:create` | ✅ | ✅ | ❌ | ❌ | ❌ | Register/create new user accounts |
| `user:read` | ✅ | ✅ | ✅ | ❌ | ❌ | View user profiles and status |
| `user:update` | ✅ | ✅ | ❌ | ❌ | ❌ | Edit user details and department assignments |
| `user:delete` | ✅ | ❌ | ❌ | ❌ | ❌ | Delete or deactivate user accounts |
| `role:assign` | ✅ | ✅ | ❌ | ❌ | ❌ | Assign roles to users (guarded against privilege escalation) |
| `role:read` | ✅ | ✅ | ❌ | ❌ | ❌ | View available roles and permission sets |
| `department:manage` | ✅ | ✅ | ❌ | ❌ | ❌ | Create and configure department records |
| `department:read` | ✅ | ✅ | ✅ | ✅ | ✅ | View department listings |
| `document:upload` | ✅ | ✅ | ✅ | Conditional | ❌ | Ingest new knowledge documents |
| `document:read` | ✅ | ✅ | ✅ | ✅ | ✅ | Read permitted documents and chunks |
| `document:delete_own` | ✅ | ✅ | ✅ | ✅ | ❌ | Delete documents owned by the user |
| `document:delete_any` | ✅ | ❌ | ❌ | ❌ | ❌ | Delete any document across the system |
| `document:grant` | ✅ | ✅ | ✅ | ❌ | ❌ | Grant explicit document permissions |
| `rag:query` | ✅ | ✅ | ✅ | ✅ | ✅ | Execute semantic queries against authorized documents |
| `audit:read` | ✅ | ❌ | ❌ | ❌ | ❌ | Inspect system security audit logs |
| `system:config` | ✅ | ❌ | ❌ | ❌ | ❌ | View/edit system configuration |

### 3.2 Privilege Escalation Prevention
- An **ADMIN** cannot assign or revoke the `SUPER_ADMIN` role.
- An **ADMIN** cannot modify, deactivate, or delete a `SUPER_ADMIN` user.
- A user cannot elevate their own roles.
- The system prevents deleting or deactivating the sole remaining active `SUPER_ADMIN`.

---

## 4. Department-Level Access Control

Departments are dynamic database entities (`departments` table) rather than hardcoded rules.

### 4.1 Configurable Departments
1. **HR** (Human Resources)
2. **IT** (Information Technology & Infrastructure)
3. **AV** (Acoustic / Audio-Visual Systems)
4. **AIRPORT** (Airport Systems Engineering)
5. **LIGHT** (Lighting Design & Engineering)
6. **MEP** (Mechanical, Electrical, and Plumbing)
7. **MGMT** (Executive Management)
8. **ADMIN_GEN** (General Administration)

### 4.2 Multi-Membership Architecture
- Users can belong to one or more departments via `user_departments` (with a designated `is_primary` flag).
- Documents can be associated with one or more departments via `document_departments`.
- Cross-department projects allow sharing a document across multiple specific departments (e.g., MEP + Lighting + Airport Systems) without making it company-wide.

---

## 5. Document-Level Security & Deterministic Retrieval Filtering

### 5.1 Visibility Classifications
Every document ingested into Sankalit Intelligence possesses a strict visibility classification:

1. **`PUBLIC`**: Accessible to any authenticated user in the organization.
2. **`COMPANY`**: Accessible to regular company members (`EMPLOYEE`, `MANAGER`, `ADMIN`, `SUPER_ADMIN`).
3. **`DEPARTMENT`**: Accessible **only** to users whose assigned departments intersect with the document's assigned departments (or the document's creator).
4. **`RESTRICTED`**: Confidential document accessible **only** to the document creator and users/roles explicitly granted permission in `document_permissions`.

### 5.2 Critical RAG Retrieval Filtering Protocol

```
+--------------------------------------------------------------+
|                    Incoming RAG Query Request                 |
+--------------------------------------------------------------+
                                |
                                v
               [Step 1: Authenticate Identity]
                Verify JWT access token & claims
                                |
                                v
         [Step 2: Resolve User Roles & Departments]
          Query user_roles and user_departments tables
                                |
                                v
     [Step 3: Deterministic SQL Document Authorization]
      Execute get_authorized_document_ids(user) via SQL:
      - Owner ID = user.id
      - Visibility = 'PUBLIC'
      - Visibility = 'COMPANY' (if role >= EMPLOYEE)
      - Visibility = 'DEPARTMENT' AND dept_id IN (user_dept_ids)
      - Explicit Grants in document_permissions
                                |
                                v
              Returns strict List[int] allowed_ids
            (If allowed_ids is empty -> return immediately!)
                                |
                                v
   [Step 4: Vector Similarity Search Filtered at SQL Layer]
     SELECT chunk_id, document_id, text, embedding
     FROM document_chunks
     WHERE document_id IN (:allowed_ids)
                                |
                                v
  [Step 5: Cosine Similarity Ranking (Only Authorized Chunks)]
                                |
                                v
  [Step 6: Local Prompt Construction & Ollama LLM Inference]
    Context constructed strictly from authorized chunks
                                |
                                v
              [Grounded Answer + Permitted Sources]
```

> [!IMPORTANT]
> **Zero Context Leakage Guarantee**:
> Unauthorized document chunks are excluded inside SQLite with `WHERE document_id IN (...)`. They are never deserialized from JSON, never loaded into Python memory, never evaluated for cosine similarity, and never reach the Ollama context prompt.

---

## 6. Database Schema Design

```
+---------------------+          +----------------------+
|       users         |          |        roles         |
+---------------------+          +----------------------+
| id (PK)             |<----+    | id (PK)              |<----+
| username            |     |    | name                 |     |
| email               |     |    | description          |     |
| hashed_password     |     |    +----------------------+     |
| full_name           |     |               |                 |
| is_active           |     |               |                 |
| is_superuser        |     |    +----------------------+     |
| failed_login_att... |     |    |   role_permissions   |     |
| locked_until        |     |    +----------------------+     |
+---------------------+     |    | role_id (FK) --------+     |
         |                  |    | permission_id (FK) --+     |
         |                  |    +----------------------+     |
         v                  |                                 |
+---------------------+     |    +----------------------+     |
|     user_roles      |     |    |     permissions      |     |
+---------------------+     |    +----------------------+     |
| user_id (FK) -------+-----+    | id (PK) <------------+     |
| role_id (FK) -------+-----+--->| name                 |
+---------------------+          | description          |
                                 +----------------------+

+---------------------+          +----------------------+
|     departments     |          |   user_departments   |
+---------------------+          +----------------------+
| id (PK) <-----------+-----+    | user_id (FK) --------+--> (users.id)
| name                |     +--->| department_id (FK)   |
| code                |          | is_primary           |
+---------------------+          +----------------------+
         ^
         |
+-------------------------+      +----------------------+
|  document_departments   |      |      documents       |
+-------------------------+      +----------------------+
| document_id (FK) -------+----->| id (PK)              |
| department_id (FK) -----+      | filename             |
+-------------------------+      | file_type            |
                                 | content_hash (UNIQUE)|
+-------------------------+      | character_count      |
|  document_permissions   |      | owner_id (FK) -------+--> (users.id)
+-------------------------+      | visibility           |
| id (PK)                 |      | access_policy        |
| document_id (FK) -------+----->| status               |
| user_id (FK) -----------+      | created_at           |
| role_id (FK) -----------+      +----------------------+
| permission_type         |                 |
+-------------------------+                 v
                                 +----------------------+
+-------------------------+      |   document_chunks    |
|      refresh_tokens     |      +----------------------+
+-------------------------+      | id (PK)              |
| id (PK)                 |      | document_id (FK) ----+
| user_id (FK) -----------+      | chunk_index          |
| token_hash              |      | text                 |
| expires_at              |      | character_count      |
| is_revoked              |      | token_count          |
+-------------------------+      | embedding (JSON)     |
                                 +----------------------+
+-------------------------+
|       audit_logs        |
+-------------------------+
| id (PK)                 |
| actor_id (FK, nullable) |
| actor_username          |
| action                  |
| resource_type           |
| resource_id             |
| details_json            |
| ip_address              |
| status                  |
| created_at              |
+-------------------------+
```

---

## 7. Audit Logging & Security Event Monitoring

The `audit_logs` table provides an immutable record of security-critical actions:
- User logins (`LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGIN_BLOCKED`).
- Token refreshes and revocations (`LOGOUT`, `TOKEN_REFRESH`).
- Password changes and administrative password resets (`PASSWORD_CHANGE`, `PASSWORD_RESET`).
- User creation, update, and deactivation (`USER_CREATE`, `USER_UPDATE`, `USER_DELETE`).
- Document ingestion, permission grants, and deletions (`DOCUMENT_UPLOAD`, `DOCUMENT_PERMISSION_GRANT`, `DOCUMENT_DELETE`).
- Semantic RAG queries (`RAG_QUERY`).

### Credential Redaction Guarantee
All audit log entries pass through `sanitize_details()` which automatically strips and replaces sensitive keys (`password`, `new_password`, `token`, `secret`, `hashed_password`) with `[REDACTED]`.

---

## 8. Milestone 3 Security Hardening & Remediation

### 8.1 Security Audit Findings & Fixes
During Milestone 3 Phase 1 verification, an end-to-end security audit was conducted on authentication, token lifecycle, and audit integrity:

1. **Bootstrap Privilege Escalation Prevention**:
   - *Vulnerability*: The initial bootstrap logic allowed the first registered user to become `SUPER_ADMIN`. However, a race condition or unvalidated registration call could permit attackers to claim `SUPER_ADMIN` if total user count checks were race-prone.
   - *Remediation*: `register_user` in `app/services/auth_service.py` was updated to explicitly query `SELECT 1 FROM user_roles ur JOIN roles r ON ur.role_id = r.id WHERE r.name = 'SUPER_ADMIN'`. If a `SUPER_ADMIN` already exists in the system, any subsequent registration requesting `SUPER_ADMIN` without an authenticated `SUPER_ADMIN` caller is rejected immediately with a permission violation.

2. **Atomic Refresh Token Rotation (Anti-Replay Defense)**:
   - *Vulnerability*: A non-atomic read-then-update pattern in token rotation allowed concurrent requests with the identical refresh token to both succeed before revocation committed.
   - *Remediation*: In `app/security/tokens.py`, rotation executes an atomic SQL update:
     ```sql
     UPDATE refresh_tokens
     SET revoked_at = CURRENT_TIMESTAMP
     WHERE id = ? AND revoked_at IS NULL
     ```
     If `cursor.rowcount == 0`, the token is recognized as already revoked or invalid, the rotation fails, and potential token replay attacks are blocked.

3. **Database-Engine Immutability Triggers on Audit Logs**:
   - *Requirement*: Audit logs must be tamper-proof and immutable even if application code is modified.
   - *Remediation*: Two SQLite database triggers were created in `app/security/database.py`:
     ```sql
     CREATE TRIGGER IF NOT EXISTS prevent_audit_log_update
     BEFORE UPDATE ON audit_logs
     BEGIN
         SELECT RAISE(ABORT, 'Audit log records are immutable and cannot be updated.');
     END;

     CREATE TRIGGER IF NOT EXISTS prevent_audit_log_delete
     BEFORE DELETE ON audit_logs
     BEGIN
         SELECT RAISE(ABORT, 'Audit log records are immutable and cannot be deleted.');
     END;
     ```
     Any SQL attempt to update or delete rows in `audit_logs` raises an unbypassable SQLite `DatabaseError`.

4. **Document Metadata & Visibility Escalation Defense**:
   - *Requirement*: Non-management users must not edit document metadata, and non-administrators must not escalate document visibility to `PUBLIC`.
   - *Remediation*: `update_document_metadata` in `app/services/document_service.py` enforces ownership and management rights before editing. Attempting to set `visibility = 'PUBLIC'` is restricted to `SUPER_ADMIN` and `ADMIN` roles; unauthorized callers receive HTTP 403 / `PermissionError`.

5. **Prompt Injection & Indirect Jailbreak Containment**:
   - *Mitigation*: In `app/ai/context_builder.py`, all retrieved document content is wrapped in `<evidence>` XML boundary tags preceded by a strict security disclaimer instructing the LLM to ignore any instructions embedded inside document text.
   - Pre-retrieval and post-retrieval filtering detects known adversarial jailbreak patterns (`ignore previous instructions`, `reveal system prompt`, `developer mode`, `override permissions`).



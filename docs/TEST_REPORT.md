# Sankalit Intelligence — Quality Assurance & Test Report

**Milestone 2**: Authentication, RBAC, and Document-Level Security  
**Execution Environment**: Windows 11, Python 3.11.9 (`.venv`)  
**Hardware Profile**: Intel Core i5-1235U, ~8 GB RAM, CPU-only  
**Local Inference**: Ollama (`qwen3:1.7b`, `nomic-embed-text`)  
**Database**: SQLite 3 (`data/sankalit.db`)  
**Timestamp**: 2026-11-13  

---

## 1. Executive Summary

A comprehensive test suite containing **64 automated unit, integration, and API tests** was authored and executed. All 64 tests passed with **0 failures and 0 errors**.

Additionally, a live end-to-end multi-user security verification was executed against running local Ollama services, confirming:
1. Multi-department user creation (HR, IT, Management).
2. Department-level document isolation (`DEPARTMENT` visibility).
3. Pre-retrieval SQL filtering (unauthorized user receives 0 chunks).
4. Negative context rejection (unauthorized user gets `"The available documents do not contain enough information..."`).
5. Grounded RAG answer with source citation for authorized HR user.
6. Role-based document deletion protection (unauthorized user rejected with `False`).
7. Comprehensive audit logging with credential redaction.

```
======================================================================
Ran 64 tests in 31.809s

OK (Pass Rate: 100%, Failures: 0, Errors: 0)
======================================================================
```

---

## 2. Test Suite Breakdown (64 Automated Tests)

### 2.1 Authentication & Password Security (`tests/test_auth.py` - 7 Tests)
- **Status**: PASSED (7/7)
- **Coverage**:
  1. `test_argon2id_hashing_and_verification`: Verified Argon2id password hashing parameters (`time_cost=2`, `memory_cost=65536`, `parallelism=1`) and negative verification.
  2. `test_password_strength_validation`: Verified enforcement of 8+ characters, uppercase, lowercase, numbers, and special characters.
  3. `test_jwt_access_token_creation_and_expiration`: Verified JWT claims, validity period, and expired token rejection.
  4. `test_bootstrap_superadmin_registration`: Verified first registered user automatically becomes active `SUPER_ADMIN`.
  5. `test_failed_login_and_account_lockout`: Verified counter increments on failed login and account lockout triggers after 5 consecutive failures.
  6. `test_refresh_token_rotation_and_revocation`: Verified single-use refresh token rotation, replay rejection, and logout revocation.
  7. `test_change_password_and_admin_reset`: Verified self-service password update and offline administrator password reset.

### 2.2 Role-Based Access Control (`tests/test_rbac.py` - 3 Tests)
- **Status**: PASSED (3/3)
- **Coverage**:
  1. `test_seed_roles_and_permissions`: Verified default seeding of 5 roles, 16 permissions, and role-permission mappings.
  2. `test_role_hierarchy_and_privilege_escalation`: Verified Admin cannot assign or revoke Super Admin, nor manage Super Admin accounts.
  3. `test_department_management_and_user_assignment`: Verified dynamic department creation, user department multi-membership, and primary department flags.

### 2.3 Document-Level Security & SQL Filtering (`tests/test_document_security.py` - 6 Tests)
- **Status**: PASSED (6/6)
- **Coverage**:
  1. `test_public_document_access`: Verified `PUBLIC` documents are accessible to any active user.
  2. `test_company_document_access`: Verified `COMPANY` documents are accessible to regular members but hidden from viewers without explicit grants.
  3. `test_cross_department_isolation`: Verified HR department documents are accessible to HR employees but completely invisible to IT employees.
  4. `test_explicit_document_permission_grant`: Verified `RESTRICTED` documents become accessible only when explicit user/role grant exists in `document_permissions`.
  5. `test_pre_retrieval_sql_filtering_guarantee`: Verified `search_similar_chunks` with `allowed_document_ids` filters strictly inside SQLite, never loading unauthorized chunks into memory.
  6. `test_document_deletion_authorization`: Verified document owners and Super Admins can delete documents, while other users are rejected.

### 2.4 Audit Logging (`tests/test_audit.py` - 2 Tests)
- **Status**: PASSED (2/2)
- **Coverage**:
  1. `test_audit_event_logging_and_filtering`: Verified recording of security events, status filtering, and chronological ordering.
  2. `test_credential_redaction_in_audit_logs`: Verified automatic redaction of `password`, `token`, `secret`, and `hashed_password` keys in audit metadata.

### 2.5 Security API Endpoints (`tests/test_security_api.py` - 4 Tests)
- **Status**: PASSED (4/4)
- **Coverage**:
  1. `test_api_login_success_and_failure`: Verified `/auth/login` endpoint returns valid access token on correct credentials and 401 on invalid.
  2. `test_api_auth_me_profile`: Verified `/auth/me` returns caller profile, roles, departments, and permissions.
  3. `test_api_cross_department_rag_retrieval_isolation`: Verified end-to-end API RAG query: IT user receives `insufficient_context` for HR document, while HR user retrieves the answer.
  4. `test_api_unauthorized_user_creation_rejected`: Verified non-admin users cannot create new user accounts via `/users` (403 Forbidden).

### 2.6 Core RAG API Endpoints (`tests/test_api.py` - 9 Tests)
- **Status**: PASSED (9/9)
- **Coverage**:
  1. `test_root_endpoint`: `GET /` returns running status.
  2. `test_health_endpoint`: `GET /health` returns healthy status.
  3. `test_health_ollama_endpoint`: `GET /health/ollama` returns connection status.
  4. `test_chat_endpoint_empty_message`: `POST /chat` rejects empty payload (422).
  5. `test_chat_endpoint_success`: `POST /chat` returns LLM response.
  6. `test_documents_list_endpoint`: `GET /documents` returns authorized documents.
  7. `test_documents_stats_endpoint`: `GET /documents/stats` returns storage statistics.
  8. `test_documents_upload_invalid_extension`: `POST /documents/upload` rejects invalid extensions (400).
  9. `test_rag_query_endpoint`: `POST /rag/query` executes secure semantic retrieval and grounded answering.

### 2.7 Milestone 1 Foundation Modules (33 Tests)
- `tests/test_document_loader.py` (5/5 PASSED): PDF and DOCX extraction, corruption checks, extension validation.
- `tests/test_chunker.py` (4/4 PASSED): Text chunking, 1000-char window, 150-char overlap, word-boundary preservation.
- `tests/test_embedder.py` (6/6 PASSED): nomic-embed-text 768-dim embeddings, dimension validation, empty/whitespace handling.
- `tests/test_vector_store.py` (5/5 PASSED): Cosine similarity, schema initialization, duplicate prevention, cascading deletion.
- `tests/test_ingestion.py` (5/5 PASSED): End-to-end file ingestion, SHA-256 deduplication, error handling.
- `tests/test_retriever.py` (4/4 PASSED): Top-K ranking, similarity thresholds, metadata formatting.
- `tests/test_rag_pipeline.py` (4/4 PASSED): Prompt building, context grounding, source citation format, negative rejection.

---

## 3. Live Multi-User Security Verification Results

Executed via `scripts/verify_security_live.py` against running Ollama (`nomic-embed-text` and `qwen3:1.7b`):

```
================================================================================
SANKALIT INTELLIGENCE — MILESTONE 2: LIVE MULTI-USER SECURITY VERIFICATION
================================================================================

[STEP 1] Initializing isolated database at: data\test_live_security.db
✓ Schema initialized and migrations applied: RAG + security tables created.

[STEP 2] Setting up multi-department users...
  Available Roles: ['ADMIN', 'EMPLOYEE', 'MANAGER', 'SUPER_ADMIN', 'VIEWER']
  Available Departments: ['ADMIN_GEN', 'AIRPORT', 'AV', 'HR', 'IT', 'LIGHT', 'MEP', 'MGMT']
✓ Created HR User: hr_lead@sankalit.com (ID: 1, Dept: HR)
✓ Created IT User: it_engineer@sankalit.com (ID: 2, Dept: IT)
✓ Created Super Admin: superadmin@sankalit.com (ID: 3, Role: SUPER_ADMIN)

[STEP 3] Testing Authentication & JWT Access Tokens...
✓ Authenticated HR User: hr_lead. Roles: ['EMPLOYEE'], Departments: ['HR']
✓ Authenticated IT User: it_engineer. Roles: ['EMPLOYEE'], Departments: ['IT']

[STEP 4] Ingesting Confidential HR Document via nomic-embed-text...
  Generating real 768-dim embedding via Ollama nomic-embed-text...
  Generated embedding with 768 dimensions.
✓ HR Document saved with ID: 1 (Visibility: DEPARTMENT, Dept: HR)

[STEP 5] Testing Pre-Retrieval Document Authorization Filtering...
  HR User Authorized Document IDs: [1]
  IT User Authorized Document IDs: []
  Super Admin Authorized Document IDs: [1]
✓ SQL-level authorization filtering verified: IT user has 0 accessible documents.

[STEP 6] Executing RAG query as IT USER: 'What is the annual retention bonus percentage for HR staff?'
  Retrieving chunks with IT user's allowed_document_ids...
  Retrieved chunks for IT user: 0
  Calling full RAG pipeline for IT user...
  IT User RAG Status: insufficient_context
  IT User RAG Answer: The available documents do not contain enough information to answer this question.
  IT User RAG Sources: []
✓ Verified: IT user received ZERO chunks and NO confidential HR data reached the LLM context!

[STEP 7] Executing RAG query as HR USER: 'What is the annual retention bonus percentage for HR staff?'
  Retrieving chunks with HR user's allowed_document_ids...
  Retrieved chunks for HR user: 1
  Chunk 0 Similarity: 0.7473
  Generating local LLM answer via Ollama qwen3:1.7b...
  HR User RAG Status: success
  HR User RAG Answer:
    The annual retention bonus percentage for HR staff is 28 percent, as stated in the document: [Source: Sankalit_HR_Compensation_2026.pdf, Chunk 0].
  HR User RAG Sources:
    [{'filename': 'Sankalit_HR_Compensation_2026.pdf', 'chunk_index': 0, 'similarity': 0.747346}]
✓ Verified: HR user received precise grounded answer citing the HR document!

[STEP 8] Testing Document Deletion Authorization...
  IT User can manage HR doc?    False (Expected: False)
  HR User can manage HR doc?    True (Expected: True - is Owner)
  Super Admin can manage HR doc? True (Expected: True - is Super Admin)
✓ Document deletion access control verified.

[STEP 9] Inspecting Security Audit Logs...
  Total audit log records captured: 3
  - [2026-11-13 10:01:00] Actor: 1, Action: DOCUMENT_UPLOAD, Resource: document:1, Status: SUCCESS
  - [2026-11-13 10:00:58] Actor: 2, Action: LOGIN_SUCCESS, Resource: AUTH:None, Status: SUCCESS
  - [2026-11-13 10:00:58] Actor: 1, Action: LOGIN_SUCCESS, Resource: AUTH:None, Status: SUCCESS
✓ Audit trail verified.

================================================================================
ALL LIVE MULTI-USER SECURITY VERIFICATIONS COMPLETED SUCCESSFULLY!
================================================================================
```

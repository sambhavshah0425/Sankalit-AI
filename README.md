# Sankalit Intelligence

> Fully local, privacy-first AI knowledge and productivity platform for **Sankalit Consultant**.  
> Incorporating Multi-User Identity, Role-Based Access Control (RBAC), Document-Level Security, Company Knowledge Architecture, and Domain-Aware RAG.

---

## 1. Project Overview

**Sankalit Intelligence** is an internal, local-first artificial intelligence platform designed to serve as the centralized knowledge repository and engineering productivity assistant for **Sankalit Consultant**, a multidisciplinary consultancy specializing in Acoustics, Audio-Visual Systems, Airport Systems, Architectural Lighting, Mechanical, Electrical, Plumbing (MEP), and Information Technology infrastructure design.

The platform is designed to execute entirely on local hardware (tested on an Intel Core i5-1235U laptop with ~8 GB RAM, running Windows 11) using local models via [Ollama](https://ollama.ai). No proprietary cloud AI APIs (OpenAI, Anthropic, Gemini), third-party authentication services, or external vector databases are used. All documents, embeddings, and chat interactions remain within the organization's private environment.

---

## 2. Features Actually Implemented

### Implemented in Milestone 1 (Local RAG Pipeline)
- **Document Ingestion**: Parsing of PDF documents (via `pypdf`) and Word documents (via `python-docx`).
- **Text Chunking**: Sliding-window chunking with configurable size (1,000 characters) and overlap (150 characters) preserving word boundaries.
- **Local Embeddings**: 768-dimensional vector generation using `nomic-embed-text` via Ollama HTTP API.
- **Content Deduplication**: SHA-256 document content hashing to prevent duplicate embedding computations.
- **Vector Storage**: SQLite-based transactional chunk and embedding storage with in-memory cosine similarity search.
- **Local RAG Inference**: Context assembly and response generation using `qwen3:1.7b` with citation formatting `[Source: <filename>, Chunk <index>]`.

### Implemented in Milestone 2 (Authentication, RBAC & Document Security)
- **User Authentication**: Argon2id password hashing (`argon2-cffi`), JWT access tokens (`pyjwt`), and cryptographic refresh tokens.
- **Brute-Force Protection**: Automatic account lockout after 5 consecutive failed attempts for 15 minutes.
- **Role-Based Access Control (RBAC)**: 5 distinct roles (`SUPER_ADMIN`, `ADMIN`, `MANAGER`, `EMPLOYEE`, `VIEWER`) and 20 granular permissions.
- **Department Isolation**: Multi-department membership assignments and departmental resource access policies.
- **Document-Level Security**: 4 visibility tiers (`PUBLIC`, `COMPANY`, `DEPARTMENT`, `RESTRICTED`) with deterministic pre-retrieval SQL filtering.
- **Audit Logging**: Immutable audit logging of authentication, document, and administrative events with sensitive data redaction.

### Implemented in Milestone 3 (Company Knowledge Architecture & Domain-Aware RAG)
- **Security Hardening**:
  - First-admin bootstrap privilege escalation defense preventing public registration from claiming `SUPER_ADMIN`.
  - Atomic refresh token rotation (`UPDATE ... WHERE id = ? AND revoked_at IS NULL`) preventing concurrent token replay attacks.
  - SQLite database-level immutability triggers (`prevent_audit_log_update`, `prevent_audit_log_delete`) preventing audit trail tampering.
  - Centralized document metadata update authorization preventing unauthorized `PUBLIC` visibility escalation.
- **Sankalit AI Identity Engine (`app/ai/`)**:
  - Dynamic company profile loader fetching verified corporate identity from SQLite `company_profile`.
  - Dynamic system prompt construction with Company-First response policies and prompt injection resistance.
  - Query classification engine categorizing queries into 9 distinct functional domains without LLM overhead.
  - Query normalization expanding technical acronyms (`RT60`, `BHS`, `AODB`, `STC`, `DBR`, `BOQ`, `MEP`, `SOP`, `POSH`).
  - Budgeted XML context builder (`MAX_CONTEXT_CHARACTERS = 4800`) encapsulating evidence in `<evidence>` tags.
  - Citation validator verifying cited files and chunks against actual evidence to detect hallucinations.
- **Knowledge Taxonomy**:
  - 10 functional domains and 50 subcategories representing Sankalit Consultant's multidisciplinary engineering disciplines.
  - Extended document metadata schema (`domain_id`, `category_id`, `project_name`, `project_identifier`, `document_type`, `document_date`, `document_version`, `confidentiality_level`, `classification_status`).
- **Heuristic Classification Service**:
  - Lightweight keyword heuristics assigning domains and confidence scores (`CLASSIFIED`, `NEEDS_REVIEW`, `UNCLASSIFIED`).
  - Administrative review queue and approval/reclassification endpoints.
- **Evaluation Benchmark Suite**:
  - 12 synthetic domain-specific test suites in `evaluation/datasets/` and automated benchmark runner `evaluation/evaluate_rag.py`.

---

## 3. Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                        FastAPI Gateway                                            |
|                  Authentication (Argon2id + JWT) & RBAC Permissions Check                         |
+---------------------------------------------------------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
+--------------------------------------------------+     +----------------------------------+
|             Query Understanding                  |     |       Document Ingestion         |
|  - 9-Class Intent Classification (Regex Engine)  |     |  - PDF / DOCX Text Extractors    |
|  - Acronym & Synonym Normalization               |     |  - SHA-256 Deduplication         |
|  - Dynamic System Prompt (from company_profile)  |     |  - Word-Boundary Chunker         |
+--------------------------------------------------+     |  - Heuristic Classifier (10 Dom) |
                         |                               +----------------------------------+
                         v                                                 |
+--------------------------------------------------+                       v
|          Pre-Retrieval SQL Authorization         |     +----------------------------------+
|  Filters allowed_document_ids at database layer  |     |   Local Embedding Generation     |
|  Optional filters: domain, category, project     | <-- |   Ollama nomic-embed-text        |
+--------------------------------------------------+     +----------------------------------+
                         |                                                 |
                         v                                                 v
+---------------------------------------------------------------------------------------------------+
|                                    SQLite Database (data/sankalit.db)                             |
|  - documents & document_chunks (JSON vector storage & in-memory cosine similarity)                |
|  - users, roles, permissions, departments, audit_logs (immutable triggers)                        |
|  - knowledge_domains, knowledge_categories, company_profile                                       |
+---------------------------------------------------------------------------------------------------+
                         |
                         v
+---------------------------------------------------------------------------------------------------+
|                                      Context & Generation Layer                                   |
|  - Budgeted XML Context Builder (<= 4800 characters, <evidence> containers)                       |
|  - Local Ollama qwen3:1.7b Inference (num_ctx: 2048, CPU-only)                                    |
|  - Ground-Truth Citation Validator (verifies cited chunks vs retrieved context)                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 4. Technology Stack

| Layer | Component | Specification |
|---|---|---|
| **Operating System** | Windows 11 | Host environment |
| **Runtime** | Python 3.11.9 | Standard CPython virtual environment (`.venv`) |
| **Web Framework** | FastAPI 0.100+ | Asynchronous REST API server with Pydantic validation |
| **ASGI Server** | Uvicorn | Lightweight asynchronous server |
| **Local LLM Engine** | Ollama | Local AI model runtime (`http://localhost:11434`) |
| **Chat Model** | `qwen3:1.7b` | Local CPU-friendly 1.7-billion parameter language model |
| **Embedding Model** | `nomic-embed-text` | 768-dimensional local text embeddings |
| **Database** | SQLite 3 | Embedded database (`data/sankalit.db`) with immutability triggers |
| **Password Hashing** | Argon2id | Memory-hard key derivation via `argon2-cffi` |
| **Tokens** | PyJWT | HS256 signed JSON Web Tokens |
| **Document Parsers** | `pypdf`, `python-docx` | Local PDF and DOCX text extraction |

---

## 5. Local Ollama Setup

The application requires Ollama to be running locally before starting the server.

### 5.1 Install Ollama
Download and install Ollama for Windows from [ollama.ai](https://ollama.ai).

### 5.2 Pull Required Local Models
Run the following commands in PowerShell:
```powershell
ollama pull qwen3:1.7b
ollama pull nomic-embed-text
```

### 5.3 Verify Local Models
```powershell
ollama list
```
Verify that both `qwen3:1.7b` and `nomic-embed-text` appear in the output.

---

## 6. Installation & Execution

### 6.1 Clone the Repository
```powershell
git clone https://github.com/sambhavshah0425/Sankalit-AI.git
cd Sankalit-AI
```

### 6.2 Set Up Virtual Environment
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 6.3 Configure Environment Variables
Copy the template configuration file:
```powershell
Copy-Item .env.example .env
```
Adjust parameters in `.env` as required (see Section 7).

### 6.4 Initialize the Database
The database schema and default seeds (roles, permissions, departments, taxonomy, company profile) are applied automatically on startup. To verify or initialize explicitly:
```powershell
.venv\Scripts\python.exe -c "from app.rag.vector_store import initialize_database; initialize_database()"
```

### 6.5 Start the Application
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The interactive Swagger API documentation will be available at:
`http://localhost:8000/docs`

---

## 7. Environment Variables

All configuration is managed through environment variables with safe defaults:

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_PATH` | `data/sankalit.db` | Relative or absolute path to SQLite database |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL of the local Ollama instance |
| `OLLAMA_MODEL` | `qwen3:1.7b` | Chat model name for RAG generation |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model name (768 dimensions) |
| `JWT_SECRET_KEY` | *(built-in fallback)* | Minimum 32-character secret key for JWT signing |
| `JWT_ALGORITHM` | `HS256` | Cryptographic algorithm for JWTs |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Lifespan of access tokens in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Lifespan of refresh tokens in days |
| `MAX_LOGIN_ATTEMPTS` | `5` | Maximum failed logins before account lockout |
| `LOCKOUT_DURATION_MINUTES` | `15` | Duration of brute-force lockout in minutes |
| `ALLOW_OPEN_REGISTRATION` | `false` | Enable or disable public self-registration |

---

## 8. API Documentation

Detailed REST API specifications are documented in [docs/RAG_API_REFERENCE.md](docs/RAG_API_REFERENCE.md).

### Summary of Endpoint Groups (55 Routes):
- **Health & Diagnostics**: `GET /`, `GET /health`, `GET /health/ollama`, `GET /health/models`
- **Authentication**: `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/change-password`, `POST /auth/reset-password`
- **User & Department Administration**: `GET/POST /users`, `GET/PUT/DELETE /users/{id}`, `GET/POST /departments`, `GET/PUT/DELETE /departments/{id}`
- **Company Profile**: `GET /company/profile`, `PUT /company/profile`
- **Taxonomy (Domains & Categories)**: `GET/POST /knowledge/domains`, `GET/PUT/DELETE /knowledge/domains/{id}`, `GET/POST /knowledge/categories`, `GET/PUT/DELETE /knowledge/categories/{id}`
- **Document Management**: `POST /documents/upload`, `GET /documents`, `GET /documents/{id}`, `PUT /documents/{id}`, `DELETE /documents/{id}`, `GET/POST/DELETE /documents/{id}/permissions`
- **Classification Workflows**: `GET /knowledge/classification/pending`, `GET/PUT /knowledge/classification/{id}`, `POST /knowledge/classification/{id}/approve`, `POST /knowledge/classification/{id}/reclassify`
- **Semantic Search & RAG**: `POST /knowledge/search`, `POST /rag/query`
- **Audit & Analytics**: `GET /audit/logs`, `GET /knowledge/stats`, `GET /knowledge/domains/{id}/stats`

---

## 9. Security Architecture

Detailed security design is documented in [docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md).

### Key Security Guarantees:
1. **Pre-Retrieval SQL Authorization**: Document permissions are evaluated at the SQL layer before similarity calculation. Unauthorized chunks are never loaded into memory.
2. **Immutable Audit Trail**: SQLite database triggers (`prevent_audit_log_update` and `prevent_audit_log_delete`) prevent tampering or deletion of compliance logs.
3. **Atomic Token Rotation**: Refresh tokens are revoked atomically on use, mitigating replay attacks.
4. **Bootstrap Privilege Defense**: Registration logic checks for existing `SUPER_ADMIN` accounts to prevent privilege escalation.
5. **Untrusted Context Isolation**: Retrieved evidence is framed in XML boundary tags with explicit prompt-injection defense disclaimers.

---

## 10. Automated Tests & Evaluation

### 10.1 Unit & Integration Test Suite (88 Tests)
Run the complete automated test suite:
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
Covers:
- Parsers, chunker, embedder, vector store, ingestion, retriever, and RAG pipeline.
- Argon2id passwords, JWT tokens, RBAC roles, document security, and audit logging.
- Bootstrap defense, atomic rotation, audit immutability triggers, and metadata authorization.
- Taxonomy CRUD, classification heuristics, and domain-aware retrieval.

### 10.2 Repeatable RAG Evaluation Benchmark Suite
Run the multi-domain evaluation suite:
```powershell
.venv\Scripts\python.exe evaluation/evaluate_rag.py
```
Evaluates query classification, domain routing, citation validation, adversarial prompt injection defense, and refusal rate across 12 synthetic dataset files.

---

## 11. Current Limitations

1. **In-Memory Cosine Similarity**: Embeddings are stored as JSON strings in SQLite and compared using in-memory cosine similarity. While fast for hundreds of documents, scaling to tens of thousands of chunks will benefit from dedicated vector indexing (e.g. SQLite-vec).
2. **Native Text Extraction Only**: Scanned drawings, image-only PDFs, or physical blueprints require an external OCR pre-processing pipeline, which is not yet bundled.
3. **CPU Generation Speed**: Generation latency on CPU hardware (`qwen3:1.7b`) takes ~2-3 seconds per query, which is acceptable for single-user interactive queries but not designed for high-concurrency throughput without dedicated acceleration.

---

## 12. Roadmap (Planned Features)

The following capabilities are planned for future development milestones:
- **Milestone 4: Offline OCR & Multimodal Ingestion**: Integration of offline Tesseract/EasyOCR for scanned PDF architectural blueprints and drawings.
- **Milestone 5: Vector Index Optimization**: Integration of embedded SQLite vector extensions (SQLite-vec) for sub-millisecond retrieval across >50,000 document chunks.
- **Milestone 6: Cross-Encoder Reranking**: Implementation of a small, CPU-optimized cross-encoder reranker model to improve precision on complex multi-part queries.
- **Milestone 7: Local Web UI**: Development of a secure, lightweight local web interface for non-technical users.

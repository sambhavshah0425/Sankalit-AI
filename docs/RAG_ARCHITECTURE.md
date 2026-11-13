# Sankalit Intelligence — Local RAG Pipeline Architecture

## 1. Overview & Architectural Philosophy

**Sankalit Intelligence** is an enterprise-grade, privacy-first, fully local AI knowledge and productivity platform built for **Sankalit Consultant**.

The system operates strictly within local boundaries:
- **Zero Cloud Leakage**: No external API calls (no OpenAI, no Google Gemini, no cloud vector stores).
- **CPU-Optimized Inference**: Designed to run efficiently on an Intel Core i5-1235U with ~8 GB RAM and integrated graphics.
- **Traceable Grounding**: Every answer is strictly grounded in uploaded company documentation with verifiable source and chunk citations.
- **Defensive Design**: Untrusted document content is isolated from system prompts to defend against indirect prompt injection.

```
+-----------------------------------------------------------------------------------------+
|                                    CLIENT APPLICATION                                    |
+-----------------------------------------------------------------------------------------+
       | POST /documents/upload                                    | POST /rag/query
       v                                                           v
+-------------------------------+                         +-------------------------------+
|     FastAPI Security Gate     |                         |     Query Validation Gate     |
| (MIME, ext, size, sanitizing) |                         | (Length & empty query check)  |
+-------------------------------+                         +-------------------------------+
       |                                                           |
       v                                                           v
+-------------------------------+                         +-------------------------------+
|    app.rag.document_loader    |                         |       app.rag.embedder        |
|  (pypdf / python-docx parser) |                         |   (Query embedding - 768-d)   |
+-------------------------------+                         +-------------------------------+
       |                                                           |
       v                                                           v
+-------------------------------+                         +-------------------------------+
|     app.rag.ingestion         |                         |      app.rag.retriever        |
| (SHA-256 duplicate detection) |                         | (Cosine similarity top-k rank)|
+-------------------------------+                         +-------------------------------+
       |                                                           |
       v                                                           v
+-------------------------------+                         +-------------------------------+
|       app.rag.chunker         |                         |    app.rag.rag_pipeline       |
| (1000 char size, 150 overlap) |                         | (Untrusted context isolation) |
+-------------------------------+                         +-------------------------------+
       |                                                           |
       v                                                           v
+-------------------------------+                         +-------------------------------+
|       app.rag.embedder        |                         |        Local Ollama           |
| (nomic-embed-text / batches)  |                         |  (qwen3:1.7b, think: false)   |
+-------------------------------+                         +-------------------------------+
       |                                                           |
       v                                                           v
+-----------------------------------------------------------------------------------------+
|                                 SQLite Storage Layer                                    |
|                (data/sankalit.db - Foreign Keys, Cascades & Indexes)                    |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Module Responsibilities

| Module | Location | Core Responsibilities |
| :--- | :--- | :--- |
| **Document Loader** | `app/rag/document_loader.py` | Extracts plain text from `.pdf` (via `pypdf`) and `.docx` (via `python-docx`). Enforces supported file formats and detects empty/scanned documents. |
| **Chunker** | `app/rag/chunker.py` | Splits continuous text into chunks with a default target of 1,000 characters and 150-character overlap, respecting word boundaries. |
| **Embedder** | `app/rag/embedder.py` | Interfaces with local Ollama `/api/embed` using `nomic-embed-text` (768 dimensions). Implements batching (`DEFAULT_BATCH_SIZE = 16`) to protect RAM on 8GB machines. |
| **Vector Store** | `app/rag/vector_store.py` | Manages SQLite database (`data/sankalit.db`), transactional schema operations, foreign key enforcement, cosine similarity calculations, top-K search, and cascading deletes. |
| **Ingestion Pipeline** | `app/rag/ingestion.py` | End-to-end document intake: file validation, text extraction, SHA-256 hashing, duplicate avoidance, chunking, embedding validation, and transactional insertion. |
| **Retriever** | `app/rag/retriever.py` | Converts natural language queries into embeddings, queries the vector store, computes cosine similarities, filters by minimum similarity score, and returns ranked chunks. |
| **RAG Pipeline** | `app/rag/rag_pipeline.py` | Coordinates query validation, retrieval, untrusted context assembly, system prompt injection protection, local `qwen3:1.7b` inference, and citation verification. |
| **FastAPI Backend** | `app/main.py` | RESTful API gateway exposing document management, chat, health checks, stats, and RAG query endpoints with input validation and security controls. |

---

## 3. Data Flow

### 3.1 Document Ingestion Flow
1. **Upload / Path Input**: User submits a `.pdf` or `.docx` file.
2. **Security & Type Validation**: Filename sanitized via `sanitize_filename`, extension checked against `.pdf`/`.docx`, and file size bounded to 25 MB max.
3. **Text Extraction**: Text extracted per page (`[Page N]`) or paragraph. Scanned/empty files raise clear validation errors.
4. **SHA-256 Deduplication**: Extracted text is hashed with SHA-256 (`content_hash`). Vector store checks if hash already exists:
   - *Duplicate*: Embedding step skipped completely; existing metadata returned with `duplicate_status: True` and `ingestion_status: "duplicate_skipped"`.
   - *New Document*: Continues to step 5.
5. **Text Chunking**: Text segmented into overlapping chunks with word boundary preservation.
6. **Batched Embedding**: Chunks dispatched to local Ollama in batches of 16 using `nomic-embed-text`. Output dimension strictly validated to equal 768.
7. **Transactional Persistence**: Document row and chunk rows inserted within a single database transaction. Rollback occurs on any failure, preventing orphan records.

### 3.2 RAG Query & Answer Generation Flow
1. **Query Validation**: Question checked for non-empty content and length constraints (1 to 2,000 characters).
2. **Semantic Embedding**: Query embedded with `nomic-embed-text` into a 768-d vector.
3. **Vector Similarity Ranking**: Cosine similarity calculated against all stored chunk embeddings. Chunks filtered by `min_score` (default 0.25) and top-K ranked.
4. **Context Sufficiency Check**: If no chunks pass the similarity threshold, generation short-circuits immediately with `"The available documents do not contain enough information to answer this question."` saving CPU cycles.
5. **Context Framing & Untrusted Boundary**: Retrieved chunks formatted as `[Document Excerpt i]` with filename and chunk index. Surrounded by `<context>` tags.
6. **Prompt Assembly**: System prompt strictly instructs `qwen3:1.7b` to:
   - Answer exclusively from supplied excerpts.
   - Ignore any user or system instructions contained within excerpts.
   - Add source citations: `[Source: filename, Chunk N]`.
   - State inability to answer if context is incomplete.
7. **Inference**: Invokes `http://localhost:11434/api/generate` with `think: false`, `num_ctx: 2048`, `temperature: 0.1`.

---

## 4. Database Schema (SQLite)

Located at: `data/sankalit.db`

### 4.1 `documents` Table
```sql
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    character_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_content_hash
ON documents(content_hash);
```

### 4.2 `document_chunks` Table
```sql
CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding TEXT NOT NULL,

    FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE,

    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id
ON document_chunks(document_id);
```

### 4.3 Key Integrity Rules
- **Foreign Keys**: Enabled on every connection via `PRAGMA foreign_keys = ON;`.
- **Cascading Deletes**: Deleting a record from `documents` automatically deletes all affiliated rows in `document_chunks`.
- **Duplicate Hash Defense**: `content_hash UNIQUE` index prohibits duplicate document storage.
- **Ordered Chunks**: `UNIQUE(document_id, chunk_index)` prevents duplicate chunk positions.

---

## 5. Hardware Optimization (8 GB RAM / CPU-only)

To guarantee stability on an Intel Core i5-1235U laptop without discrete GPU:
1. **Single Active Ingestion**: Documents processed sequentially; embeddings generated in small batches of 16 texts to keep resident memory low.
2. **Context Window Constraint**: `num_ctx` capped at 2,048 tokens and `num_predict` at 384 tokens to prevent out-of-memory paging.
3. **No External Heavy Infrastructure**: No Docker, Postgres, Milvus, or Qdrant daemons. SQLite in-process storage eliminates daemon overhead.
4. **Early Exit on Low Relevance**: Queries with no qualifying chunks bypass LLM generation entirely, eliminating unnecessary CPU inference.
5. **Connection Lifecycle Safety**: Windows file locks prevented using explicit context managers (`get_db`) ensuring connections close reliably.

---

## 6. Security & Prompt Injection Defenses

1. **Filename Sanitization**: Uploaded filenames stripped of path traversal characters (`..`, `/`, `\`, null bytes) and non-alphanumeric characters.
2. **File Size Enforcement**: 25 MB hard cap enforced during stream ingestion.
3. **Extension & Format Verification**: Restricted strictly to `.pdf` and `.docx`.
4. **Untrusted Data Boundary**: Documents are marked as untrusted data within `<context>` blocks. System prompt forbids the LLM from executing or adhering to commands embedded inside document text.
5. **Deterministic Grounding**: LLM is instructed with temperature 0.1 to avoid creative fabrication or speculative policies.


import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from app.config import DATABASE_PATH

EXPECTED_EMBEDDING_DIM = 768


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Create a raw connection to the SQLite database with row factory and foreign keys enabled.
    Caller is responsible for closing this connection.
    """
    target_path = Path(db_path) if db_path else DATABASE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(target_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


@contextmanager
def get_db(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that yields a database connection and guarantees it is closed on exit.
    Essential on Windows to prevent WinError 32 file lock issues.
    """
    connection = get_connection(db_path)
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(db_path: Optional[Path] = None) -> None:
    """Create the document and chunk tables, necessary indexes, and run migrations."""
    with get_db(db_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                character_count INTEGER NOT NULL,
                owner_id INTEGER,
                visibility TEXT NOT NULL DEFAULT 'COMPANY',
                access_policy TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
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
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_document_id
            ON document_chunks(document_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_content_hash
            ON documents(content_hash)
        """)
        connection.commit()

    # Apply RBAC, users, departments, and security schema migrations
    from app.security.database import migrate_database_schema
    migrate_database_schema(db_path)


def calculate_cosine_similarity(
    vector_a: List[float],
    vector_b: List[float]
) -> float:
    """
    Calculate cosine similarity between two numeric vectors.
    Returns 0.0 for zero-magnitude vectors.
    Raises ValueError if lengths do not match or vectors are empty.
    """
    if not vector_a or not vector_b:
        raise ValueError("Vectors must not be empty.")

    if len(vector_a) != len(vector_b):
        raise ValueError(
            f"Vector dimensions do not match: {len(vector_a)} != {len(vector_b)}"
        )

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    magnitude_a = math.sqrt(sum(a * a for a in vector_a))
    magnitude_b = math.sqrt(sum(b * b for b in vector_b))

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def get_document_by_hash(
    content_hash: str,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve document metadata by SHA-256 content hash."""
    with get_db(db_path) as connection:
        row = connection.execute(
            """
            SELECT d.id, d.filename, d.file_type, d.content_hash, d.character_count,
                   d.owner_id, d.visibility, d.status, d.created_at,
                   COUNT(c.id) as chunk_count
            FROM documents d
            LEFT JOIN document_chunks c ON d.id = c.document_id
            WHERE d.content_hash = ?
            GROUP BY d.id
            """,
            (content_hash,)
        ).fetchone()

        if row:
            return dict(row)
        return None


def get_document(
    document_id: int,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve document metadata, chunk count, department, and taxonomy associations by ID."""
    with get_db(db_path) as connection:
        row = connection.execute(
            """
            SELECT d.id, d.filename, d.file_type, d.content_hash, d.character_count,
                   d.owner_id, d.visibility, d.access_policy, d.status, d.created_at, d.updated_at,
                   d.document_title, d.domain_id, d.category_id, d.project_name, d.project_identifier,
                   d.document_type, d.document_date, d.document_version, d.confidentiality_level,
                   d.classification_status, d.classification_confidence, d.classification_explanation,
                   kd.name as domain_name, kd.slug as domain_slug,
                   kc.name as category_name, kc.slug as category_slug,
                   u.username as owner_username,
                   COUNT(c.id) as chunk_count
            FROM documents d
            LEFT JOIN document_chunks c ON d.id = c.document_id
            LEFT JOIN users u ON u.id = d.owner_id
            LEFT JOIN knowledge_domains kd ON kd.id = d.domain_id
            LEFT JOIN knowledge_categories kc ON kc.id = d.category_id
            WHERE d.id = ?
            GROUP BY d.id
            """,
            (document_id,)
        ).fetchone()

        if not row:
            return None

        doc_dict = dict(row)
        # Fetch associated departments
        dept_rows = connection.execute(
            """
            SELECT d.id, d.name, d.code
            FROM departments d
            JOIN document_departments dd ON dd.department_id = d.id
            WHERE dd.document_id = ?
            """,
            (document_id,)
        ).fetchall()
        doc_dict["departments"] = [dict(r) for r in dept_rows]
        return doc_dict


def list_documents(
    allowed_document_ids: Optional[List[int]] = None,
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    project_name: Optional[str] = None,
    document_type: Optional[str] = None,
    classification_status: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    List indexed documents with metadata, optionally filtered by user-authorized document IDs
    and domain/project/type criteria.
    If allowed_document_ids is provided as an empty list, returns [] immediately.
    """
    if allowed_document_ids is not None and len(allowed_document_ids) == 0:
        return []

    with get_db(db_path) as connection:
        query = """
            SELECT d.id, d.filename, d.file_type, d.content_hash, d.character_count,
                   d.owner_id, d.visibility, d.access_policy, d.status, d.created_at, d.updated_at,
                   d.document_title, d.domain_id, d.category_id, d.project_name, d.project_identifier,
                   d.document_type, d.document_date, d.document_version, d.confidentiality_level,
                   d.classification_status, d.classification_confidence, d.classification_explanation,
                   kd.name as domain_name, kd.slug as domain_slug,
                   kc.name as category_name, kc.slug as category_slug,
                   u.username as owner_username,
                   COUNT(c.id) as chunk_count
            FROM documents d
            LEFT JOIN document_chunks c ON d.id = c.document_id
            LEFT JOIN users u ON u.id = d.owner_id
            LEFT JOIN knowledge_domains kd ON kd.id = d.domain_id
            LEFT JOIN knowledge_categories kc ON kc.id = d.category_id
            WHERE 1=1
        """
        params: List[Any] = []

        if allowed_document_ids is not None:
            placeholders = ",".join("?" for _ in allowed_document_ids)
            query += f" AND d.id IN ({placeholders})"
            params.extend(allowed_document_ids)

        if domain_id is not None:
            query += " AND d.domain_id = ?"
            params.append(domain_id)

        if category_id is not None:
            query += " AND d.category_id = ?"
            params.append(category_id)

        if department_id is not None:
            query += """ AND d.id IN (
                SELECT document_id FROM document_departments WHERE department_id = ?
            )"""
            params.append(department_id)

        if project_name:
            query += " AND d.project_name LIKE ?"
            params.append(f"%{project_name}%")

        if document_type:
            query += " AND d.document_type = ?"
            params.append(document_type)

        if classification_status:
            query += " AND d.classification_status = ?"
            params.append(classification_status)

        query += " GROUP BY d.id ORDER BY d.created_at DESC"

        rows = connection.execute(query, params).fetchall()

        results = []
        for r in rows:
            d_dict = dict(r)
            dept_rows = connection.execute(
                """
                SELECT d.id, d.name, d.code
                FROM departments d
                JOIN document_departments dd ON dd.department_id = d.id
                WHERE dd.document_id = ?
                """,
                (r["id"],)
            ).fetchall()
            d_dict["departments"] = [dict(dept) for dept in dept_rows]
            results.append(d_dict)

        return results


def get_document_chunks(
    document_id: int,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieve all chunks for a document ordered by chunk_index."""
    with get_db(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, document_id, chunk_index, text
            FROM document_chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,)
        ).fetchall()

        return [dict(row) for row in rows]


def delete_document(
    document_id: int,
    db_path: Optional[Path] = None
) -> bool:
    """
    Delete a document by ID. Cascades to document_chunks, document_departments,
    and document_permissions via SQLite foreign keys.
    Returns True if deleted, False if document was not found.
    """
    with get_db(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM documents WHERE id = ?",
            (document_id,)
        )
        connection.commit()
        return cursor.rowcount > 0


def save_document(
    filename: str,
    file_type: str,
    content_hash: str,
    character_count: int,
    chunks: List[Dict[str, Any]],
    owner_id: Optional[int] = None,
    visibility: str = "COMPANY",
    access_policy: Optional[str] = None,
    department_ids: Optional[List[int]] = None,
    document_title: Optional[str] = None,
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    project_name: Optional[str] = None,
    project_identifier: Optional[str] = None,
    document_type: str = "general",
    document_date: Optional[str] = None,
    document_version: str = "1.0",
    confidentiality_level: str = "INTERNAL",
    classification_status: str = "UNCLASSIFIED",
    classification_confidence: float = 0.0,
    classification_explanation: Optional[str] = None,
    db_path: Optional[Path] = None
) -> int:
    """
    Save a document and its embedded chunks transactionally with security & taxonomy metadata.
    Returns document_id. If content_hash already exists, returns existing ID.
    """
    if not chunks:
        raise ValueError("Cannot save a document without chunks.")

    with get_db(db_path) as connection:
        # Check existing by content_hash
        existing = connection.execute(
            "SELECT id FROM documents WHERE content_hash = ?",
            (content_hash,)
        ).fetchone()

        if existing:
            return existing["id"]

        actual_owner_id = owner_id
        if actual_owner_id is not None:
            user_exists = connection.execute("SELECT 1 FROM users WHERE id = ?", (actual_owner_id,)).fetchone()
            if not user_exists:
                actual_owner_id = None

        try:
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    filename,
                    file_type,
                    content_hash,
                    character_count,
                    owner_id,
                    visibility,
                    access_policy,
                    status,
                    document_title,
                    domain_id,
                    category_id,
                    project_name,
                    project_identifier,
                    document_type,
                    document_date,
                    document_version,
                    confidentiality_level,
                    classification_status,
                    classification_confidence,
                    classification_explanation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    file_type,
                    content_hash,
                    character_count,
                    actual_owner_id,
                    visibility,
                    access_policy,
                    document_title or filename,
                    domain_id,
                    category_id,
                    project_name,
                    project_identifier,
                    document_type or "general",
                    document_date,
                    document_version or "1.0",
                    confidentiality_level or "INTERNAL",
                    classification_status or "UNCLASSIFIED",
                    classification_confidence or 0.0,
                    classification_explanation
                )
            )

            document_id = cursor.lastrowid

            # Associate departments
            if department_ids:
                for dept_id in department_ids:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO document_departments (document_id, department_id)
                        VALUES (?, ?)
                        """,
                        (document_id, dept_id)
                    )

            chunk_records = []
            for chunk in chunks:
                embedding = chunk.get("embedding")
                if not embedding or not isinstance(embedding, list):
                    raise ValueError(
                        f"Chunk {chunk.get('chunk_index')} has missing or invalid embedding."
                    )

                if len(embedding) != EXPECTED_EMBEDDING_DIM:
                    raise ValueError(
                        f"Chunk {chunk.get('chunk_index')} embedding dimension mismatch: "
                        f"got {len(embedding)}, expected {EXPECTED_EMBEDDING_DIM}."
                    )

                chunk_records.append((
                    document_id,
                    chunk["chunk_index"],
                    chunk["text"],
                    json.dumps(embedding)
                ))

            connection.executemany(
                """
                INSERT INTO document_chunks (
                    document_id,
                    chunk_index,
                    text,
                    embedding
                )
                VALUES (?, ?, ?, ?)
                """,
                chunk_records
            )

            connection.commit()
            return document_id

        except Exception:
            connection.rollback()
            raise


def search_similar_chunks(
    query_embedding: List[float],
    top_k: int = 5,
    min_score: float = 0.0,
    allowed_document_ids: Optional[List[int]] = None,
    domain_id: Optional[int] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    project_name: Optional[str] = None,
    document_type: Optional[str] = None,
    filename: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Find top_k most similar document chunks matching query_embedding.
    CRITICAL SECURITY GUARANTEE:
    If allowed_document_ids is provided, ONLY chunks belonging to those authorized
    documents are queried from the database. Unauthorized chunks never reach memory,
    similarity calculation, or the LLM context.
    """
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    if not query_embedding or not isinstance(query_embedding, list):
        raise ValueError("query_embedding must be a non-empty list of floats.")

    if len(query_embedding) != EXPECTED_EMBEDDING_DIM:
        raise ValueError(
            f"Query embedding dimension mismatch: got {len(query_embedding)}, "
            f"expected {EXPECTED_EMBEDDING_DIM}."
        )

    # If the user is authorized to view 0 documents, return [] immediately without DB query
    if allowed_document_ids is not None and len(allowed_document_ids) == 0:
        return []

    with get_db(db_path) as connection:
        query = """
            SELECT
                c.id AS chunk_id,
                c.document_id,
                c.chunk_index,
                c.text,
                c.embedding,
                d.filename,
                d.file_type,
                d.document_title,
                d.domain_id,
                kd.name as domain_name,
                kd.slug as domain_slug,
                d.category_id,
                kc.name as category_name,
                kc.slug as category_slug,
                d.project_name,
                d.document_version,
                d.document_type
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            LEFT JOIN knowledge_domains kd ON kd.id = d.domain_id
            LEFT JOIN knowledge_categories kc ON kc.id = d.category_id
            WHERE d.status = 'active'
        """
        params: List[Any] = []

        # 1. Authorization filter (mandatory)
        if allowed_document_ids is not None:
            placeholders = ",".join("?" for _ in allowed_document_ids)
            query += f" AND c.document_id IN ({placeholders})"
            params.extend(allowed_document_ids)

        # 2. Metadata filters
        if domain_id is not None:
            query += " AND d.domain_id = ?"
            params.append(domain_id)

        if category_id is not None:
            query += " AND d.category_id = ?"
            params.append(category_id)

        if department_id is not None:
            query += """ AND d.id IN (
                SELECT document_id FROM document_departments WHERE department_id = ?
            )"""
            params.append(department_id)

        if project_name:
            query += " AND d.project_name LIKE ?"
            params.append(f"%{project_name}%")

        if document_type:
            query += " AND d.document_type = ?"
            params.append(document_type)

        if filename:
            query += " AND d.filename LIKE ?"
            params.append(f"%{filename}%")

        rows = connection.execute(query, params).fetchall()

    results = []
    for row in rows:
        try:
            stored_embedding = json.loads(row["embedding"])
            if not isinstance(stored_embedding, list) or len(stored_embedding) != len(query_embedding):
                continue
            score = calculate_cosine_similarity(query_embedding, stored_embedding)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

        if score >= min_score:
            results.append({
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "filename": row["filename"],
                "file_type": row["file_type"],
                "chunk_index": row["chunk_index"],
                "text": row["text"],
                "similarity": round(score, 6),
                "document_title": row["document_title"],
                "domain_id": row["domain_id"],
                "domain_name": row["domain_name"],
                "domain_slug": row["domain_slug"],
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "category_slug": row["category_slug"],
                "project_name": row["project_name"],
                "document_version": row["document_version"],
                "document_type": row["document_type"]
            })

    results.sort(key=lambda item: item["similarity"], reverse=True)
    return results[:top_k]


def get_database_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return document, chunk, user, and department counts along with database path."""
    target_path = Path(db_path) if db_path else DATABASE_PATH
    with get_db(target_path) as connection:
        doc_row = connection.execute("SELECT COUNT(*) FROM documents").fetchone()
        chunk_row = connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()
        user_row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        dept_row = connection.execute("SELECT COUNT(*) FROM departments").fetchone()

        document_count = doc_row[0] if doc_row else 0
        chunk_count = chunk_row[0] if chunk_row else 0
        user_count = user_row[0] if user_row else 0
        dept_count = dept_row[0] if dept_row else 0

    return {
        "documents": document_count,
        "chunks": chunk_count,
        "users": user_count,
        "departments": dept_count,
        "database_path": str(target_path)
    }

"""Live multi-user end-to-end security verification script.
Tests multi-user authentication, department-level authorization,
deterministic SQL retrieval filtering, and local RAG generation against live Ollama.
"""

import os
import sys
import tempfile
import asyncio
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.security.database import migrate_database_schema
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, decode_access_token
from app.security.rbac import get_user_permissions, get_user_departments, can_actor_manage_target_role
from app.security.document_access import (
    get_authorized_document_ids,
    can_user_read_document,
    can_user_manage_document,
)
from app.security.audit import log_audit_event, query_audit_logs
from app.services.auth_service import authenticate_user, register_user
from app.rag.vector_store import (
    get_db,
    initialize_database,
    save_document,
    search_similar_chunks,
    delete_document,
)
from app.rag.embedder import generate_single_embedding
from app.rag.rag_pipeline import answer_query_async


async def run_live_verification():
    print("=" * 80)
    print("SANKALIT INTELLIGENCE — MILESTONE 2: LIVE MULTI-USER SECURITY VERIFICATION")
    print("=" * 80)

    # 1. Setup isolated test database
    test_db_path = Path("data/test_live_security.db")
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except Exception:
            pass
    print(f"\n[STEP 1] Initializing isolated database at: {test_db_path}")
    initialize_database(test_db_path)
    print("✓ Schema initialized and migrations applied: RAG + security tables created.")

    # 2. Setup test users and departments
    print("\n[STEP 2] Setting up multi-department users...")
    with get_db(test_db_path) as conn:
        cursor = conn.cursor()

        # Get role IDs
        cursor.execute("SELECT id, name FROM roles")
        roles = {row["name"]: row["id"] for row in cursor.fetchall()}

        # Get department IDs
        cursor.execute("SELECT id, code FROM departments")
        departments = {row["code"]: row["id"] for row in cursor.fetchall()}

        print(f"  Available Roles: {list(roles.keys())}")
        print(f"  Available Departments: {list(departments.keys())}")

        # Create HR Employee
        hr_pwd_hash = hash_password("HrSecurePass123!")
        cursor.execute(
            """INSERT INTO users (username, email, hashed_password, full_name, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            ("hr_lead", "hr_lead@sankalit.com", hr_pwd_hash, "Priya Sharma (HR)"),
        )
        hr_user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (hr_user_id, roles["EMPLOYEE"]),
        )
        cursor.execute(
            "INSERT INTO user_departments (user_id, department_id, is_primary) VALUES (?, ?, 1)",
            (hr_user_id, departments["HR"]),
        )

        # Create IT Employee
        it_pwd_hash = hash_password("ItSecurePass123!")
        cursor.execute(
            """INSERT INTO users (username, email, hashed_password, full_name, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            ("it_engineer", "it_engineer@sankalit.com", it_pwd_hash, "Rahul Verma (IT)"),
        )
        it_user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (it_user_id, roles["EMPLOYEE"]),
        )
        cursor.execute(
            "INSERT INTO user_departments (user_id, department_id, is_primary) VALUES (?, ?, 1)",
            (it_user_id, departments["IT"]),
        )

        # Create Super Admin
        admin_pwd_hash = hash_password("AdminSuperPass123!")
        cursor.execute(
            """INSERT INTO users (username, email, hashed_password, full_name, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            ("superadmin", "superadmin@sankalit.com", admin_pwd_hash, "Executive Admin"),
        )
        admin_user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (admin_user_id, roles["SUPER_ADMIN"]),
        )
        cursor.execute(
            "INSERT INTO user_departments (user_id, department_id, is_primary) VALUES (?, ?, 1)",
            (admin_user_id, departments["MGMT"]),
        )

        conn.commit()

    print(f"✓ Created HR User: hr_lead@sankalit.com (ID: {hr_user_id}, Dept: HR)")
    print(f"✓ Created IT User: it_engineer@sankalit.com (ID: {it_user_id}, Dept: IT)")
    print(f"✓ Created Super Admin: superadmin@sankalit.com (ID: {admin_user_id}, Role: SUPER_ADMIN)")

    hr_user_dict = {"id": hr_user_id, "roles": ["EMPLOYEE"], "is_superuser": False}
    it_user_dict = {"id": it_user_id, "roles": ["EMPLOYEE"], "is_superuser": False}
    admin_user_dict = {"id": admin_user_id, "roles": ["SUPER_ADMIN"], "is_superuser": True}

    # 3. Test Authentication & Token Generation
    print("\n[STEP 3] Testing Authentication & JWT Access Tokens...")
    hr_auth, hr_access_token, hr_refresh = authenticate_user("hr_lead@sankalit.com", "HrSecurePass123!", db_path=test_db_path)
    assert hr_auth is not None, "HR authentication failed"
    hr_depts = [d["name"] for d in hr_auth["departments"]]
    print(f"✓ Authenticated HR User: {hr_auth['username']}. Roles: {hr_auth['roles']}, Departments: {hr_depts}")

    it_auth, it_access_token, it_refresh = authenticate_user("it_engineer@sankalit.com", "ItSecurePass123!", db_path=test_db_path)
    assert it_auth is not None, "IT authentication failed"
    it_depts = [d["name"] for d in it_auth["departments"]]
    print(f"✓ Authenticated IT User: {it_auth['username']}. Roles: {it_auth['roles']}, Departments: {it_depts}")

    # 4. Ingest Department-Confidential Document using Local Ollama Embeddings
    print("\n[STEP 4] Ingesting Confidential HR Document via nomic-embed-text...")
    confidential_hr_text = (
        "Sankalit Engineering Compensation and Benefit Policy 2026: "
        "All HR Department staff receive a dedicated retention bonus equal to 28 percent of annual base CTC, "
        "disbursed semi-annually in June and December. "
        "Standard grievance protocols require direct escalation to the VP of People Operations within 48 hours."
    )

    print("  Generating real 768-dim embedding via Ollama nomic-embed-text...")
    embedding_768 = generate_single_embedding(confidential_hr_text)
    print(f"  Generated embedding with {len(embedding_768)} dimensions.")

    doc_id = save_document(
        filename="Sankalit_HR_Compensation_2026.pdf",
        file_type=".pdf",
        content_hash="hash_hr_comp_2026_xyz",
        character_count=len(confidential_hr_text),
        chunks=[{
            "chunk_index": 0,
            "text": confidential_hr_text,
            "character_count": len(confidential_hr_text),
            "token_count": len(confidential_hr_text) // 4,
            "embedding": embedding_768,
        }],
        db_path=test_db_path,
        owner_id=hr_user_id,
        visibility="DEPARTMENT",
        access_policy="DEPARTMENT_ONLY",
        department_ids=[departments["HR"]],
    )
    print(f"✓ HR Document saved with ID: {doc_id} (Visibility: DEPARTMENT, Dept: HR)")

    log_audit_event(
        actor_id=hr_user_id,
        action="DOCUMENT_UPLOAD",
        resource_type="document",
        resource_id=str(doc_id),
        details={"filename": "Sankalit_HR_Compensation_2026.pdf", "visibility": "DEPARTMENT"},
        db_path=test_db_path,
    )

    # 5. Authorization Evaluation: Verify Pre-Retrieval Filtering at SQL Layer
    print("\n[STEP 5] Testing Pre-Retrieval Document Authorization Filtering...")
    hr_authorized_ids = get_authorized_document_ids(hr_auth, db_path=test_db_path)
    it_authorized_ids = get_authorized_document_ids(it_auth, db_path=test_db_path)
    admin_authorized_ids = get_authorized_document_ids(admin_user_dict, db_path=test_db_path)

    print(f"  HR User Authorized Document IDs: {hr_authorized_ids}")
    print(f"  IT User Authorized Document IDs: {it_authorized_ids}")
    print(f"  Super Admin Authorized Document IDs: {admin_authorized_ids}")

    assert doc_id in hr_authorized_ids, "HR user must have access to HR department document"
    assert doc_id not in it_authorized_ids, "IT user MUST NOT have access to HR department document"
    assert doc_id in admin_authorized_ids, "Super Admin has full visibility"
    print("✓ SQL-level authorization filtering verified: IT user has 0 accessible documents.")

    # 6. Test RAG Retrieval for Unauthorized IT User
    test_query = "What is the annual retention bonus percentage for HR staff?"
    print(f"\n[STEP 6] Executing RAG query as IT USER: '{test_query}'")
    print("  Retrieving chunks with IT user's allowed_document_ids...")
    it_chunks = search_similar_chunks(
        query_embedding=generate_single_embedding(test_query),
        top_k=3,
        db_path=test_db_path,
        allowed_document_ids=it_authorized_ids,
    )
    print(f"  Retrieved chunks for IT user: {len(it_chunks)}")
    assert len(it_chunks) == 0, "Security violation: Chunks leaked to unauthorized IT user!"

    print("  Calling full RAG pipeline for IT user...")
    it_rag_response = await answer_query_async(
        query=test_query,
        top_k=3,
        db_path=test_db_path,
        allowed_document_ids=it_authorized_ids,
    )
    print(f"  IT User RAG Status: {it_rag_response['retrieval_status']}")
    print(f"  IT User RAG Answer: {it_rag_response['answer']}")
    print(f"  IT User RAG Sources: {it_rag_response['sources']}")
    assert it_rag_response["retrieval_status"] == "insufficient_context"
    assert "not contain enough information" in it_rag_response["answer"]
    assert len(it_rag_response["sources"]) == 0
    print("✓ Verified: IT user received ZERO chunks and NO confidential HR data reached the LLM context!")

    # 7. Test RAG Retrieval for Authorized HR User
    print(f"\n[STEP 7] Executing RAG query as HR USER: '{test_query}'")
    print("  Retrieving chunks with HR user's allowed_document_ids...")
    hr_chunks = search_similar_chunks(
        query_embedding=generate_single_embedding(test_query),
        top_k=3,
        db_path=test_db_path,
        allowed_document_ids=hr_authorized_ids,
    )
    print(f"  Retrieved chunks for HR user: {len(hr_chunks)}")
    assert len(hr_chunks) == 1, "HR user should retrieve the matching HR document chunk"
    print(f"  Chunk 0 Similarity: {hr_chunks[0]['similarity']:.4f}")

    print("  Generating local LLM answer via Ollama qwen3:1.7b...")
    hr_rag_response = await answer_query_async(
        query=test_query,
        top_k=3,
        db_path=test_db_path,
        allowed_document_ids=hr_authorized_ids,
    )
    print(f"  HR User RAG Status: {hr_rag_response['retrieval_status']}")
    print(f"  HR User RAG Answer:\n    {hr_rag_response['answer']}")
    print(f"  HR User RAG Sources:\n    {hr_rag_response['sources']}")

    assert hr_rag_response["retrieval_status"] == "success"
    assert len(hr_rag_response["sources"]) > 0
    assert "Sankalit_HR_Compensation_2026.pdf" == hr_rag_response["sources"][0]["filename"]
    # Check that answer mentions 28% or 28 percent
    ans_lower = hr_rag_response["answer"].lower()
    assert "28" in ans_lower, f"Expected 28% in response, got: {hr_rag_response['answer']}"
    print("✓ Verified: HR user received precise grounded answer citing the HR document!")

    # 8. Test Document Deletion Authorization
    print("\n[STEP 8] Testing Document Deletion Authorization...")
    can_it_manage = can_user_manage_document(it_auth, doc_id, db_path=test_db_path)
    can_hr_manage = can_user_manage_document(hr_auth, doc_id, db_path=test_db_path)
    can_admin_manage = can_user_manage_document(admin_user_dict, doc_id, db_path=test_db_path)

    print(f"  IT User can manage HR doc?    {can_it_manage} (Expected: False)")
    print(f"  HR User can manage HR doc?    {can_hr_manage} (Expected: True - is Owner)")
    print(f"  Super Admin can manage HR doc? {can_admin_manage} (Expected: True - is Super Admin)")

    assert not can_it_manage, "Unauthorized user should not be able to manage/delete document"
    assert can_hr_manage, "Owner should be able to manage/delete document"
    assert can_admin_manage, "Super Admin should be able to manage/delete document"
    print("✓ Document deletion access control verified.")

    # 9. Test Audit Logs
    print("\n[STEP 9] Inspecting Security Audit Logs...")
    logs = query_audit_logs(limit=10, db_path=test_db_path)
    print(f"  Total audit log records captured: {len(logs)}")
    for entry in logs:
        print(f"  - [{entry['created_at']}] Actor: {entry['actor_id']}, Action: {entry['action']}, Resource: {entry['resource_type']}:{entry['resource_id']}, Status: {entry['status']}")
    assert len(logs) >= 1, "Audit logs must record security actions"
    print("✓ Audit trail verified.")

    # Cleanup test database
    try:
        if test_db_path.exists():
            test_db_path.unlink()
    except Exception:
        pass

    print("\n" + "=" * 80)
    print("ALL LIVE MULTI-USER SECURITY VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_live_verification())

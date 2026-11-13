"""Tests for Milestone 3 Security Verification and Remediation.

Verifies:
1. First-admin bootstrap protection (cannot register second SUPER_ADMIN publicly).
2. Atomic refresh token rotation (replay rejection).
3. Audit log immutability triggers (UPDATE and DELETE raise DatabaseError).
4. Document metadata update authorization (viewer/employee cannot update, non-admin cannot escalate to PUBLIC).
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.rag.vector_store import get_db, initialize_database
from app.services.auth_service import register_user
from app.security.tokens import create_refresh_token, rotate_refresh_token
from app.services.document_service import update_document_metadata


class TestSecurityRemediation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sec.db"
        initialize_database(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_first_admin_bootstrap_protection(self):
        """First user can bootstrap SUPER_ADMIN, but subsequent registrations cannot claim SUPER_ADMIN."""
        # 1. First user registers as SUPER_ADMIN
        admin_user = register_user(
            username="initial_superadmin",
            email="admin@sankalit.local",
            password="StrongPassword123!",
            full_name="Initial Superadmin",
            requested_roles=["SUPER_ADMIN"],
            actor=None,
            db_path=self.db_path
        )
        self.assertIn("SUPER_ADMIN", admin_user["roles"])

        # 2. Second user attempts to register as SUPER_ADMIN without an authenticated actor
        with self.assertRaises((ValueError, PermissionError)) as ctx:
            register_user(
                username="hacker_admin",
                email="hacker@sankalit.local",
                password="StrongPassword123!",
                full_name="Attacker",
                requested_roles=["SUPER_ADMIN"],
                actor=None,
                db_path=self.db_path
            )
        self.assertTrue("SUPER_ADMIN" in str(ctx.exception))

        # 3. An EMPLOYEE actor attempts to register someone as SUPER_ADMIN
        employee_actor = {
            "id": 2,
            "username": "regular_emp",
            "roles": ["EMPLOYEE"],
            "permissions": ["document:read"],
            "departments": ["IT"]
        }
        with self.assertRaises((ValueError, PermissionError)) as ctx:
            register_user(
                username="unauth_admin",
                email="unauth@sankalit.local",
                password="StrongPassword123!",
                full_name="Unauth Admin",
                requested_roles=["SUPER_ADMIN"],
                actor=employee_actor,
                db_path=self.db_path
            )
        self.assertTrue("SUPER_ADMIN" in str(ctx.exception))

    def test_audit_log_immutability_triggers(self):
        """SQLite triggers must block UPDATE and DELETE on audit_logs at the database engine level."""
        with get_db(self.db_path) as conn:
            # Insert a legitimate test log (actor_id can be NULL for system actions)
            conn.execute(
                "INSERT INTO audit_logs (actor_id, action, resource_type, resource_id, details) "
                "VALUES (NULL, 'test_action', 'document', '1', 'detail_test')"
            )
            conn.commit()

            # Attempt UPDATE directly in SQL
            with self.assertRaises(sqlite3.DatabaseError) as update_ctx:
                conn.execute("UPDATE audit_logs SET action = 'tampered' WHERE action = 'test_action'")
            self.assertIn("immutable", str(update_ctx.exception))

            # Attempt DELETE directly in SQL
            with self.assertRaises(sqlite3.DatabaseError) as delete_ctx:
                conn.execute("DELETE FROM audit_logs WHERE action = 'test_action'")
            self.assertIn("immutable", str(delete_ctx.exception))

    def test_atomic_refresh_token_rotation_and_replay_rejection(self):
        """Rotating a refresh token revokes it atomically; reusing the same token raises ValueError."""
        # Setup user in DB
        user = register_user(
            username="token_user",
            email="token_user@sankalit.local",
            password="StrongPassword123!",
            full_name="Token User",
            requested_roles=["EMPLOYEE"],
            db_path=self.db_path
        )

        # Create refresh token
        raw_refresh_token = create_refresh_token(user["id"], db_path=self.db_path)

        # First rotation succeeds
        user_id_1, new_token_1 = rotate_refresh_token(raw_refresh_token, db_path=self.db_path)
        self.assertEqual(user_id_1, user["id"])
        self.assertNotEqual(new_token_1, raw_refresh_token)

        # Replay attempt with old raw_refresh_token must fail
        with self.assertRaises(ValueError) as ctx:
            rotate_refresh_token(raw_refresh_token, db_path=self.db_path)
        self.assertIn("revoked", str(ctx.exception).lower())

    def test_document_metadata_update_authorization(self):
        """Non-management users cannot edit document metadata, and non-admins cannot elevate visibility to PUBLIC."""
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO documents (filename, file_type, content_hash, character_count, "
                "classification_status, visibility, owner_id) "
                "VALUES ('spec.pdf', 'pdf', 'dummy_hash', 1024, 'CLASSIFIED', 'INTERNAL', 50)"
            )
            doc_id = cursor.lastrowid
            conn.commit()

        # 1. Regular employee (id 99) who is not the owner cannot update metadata
        emp_user = {
            "id": 99,
            "username": "emp_user",
            "roles": ["EMPLOYEE"],
            "permissions": ["document:read", "rag:query"],
            "departments": ["IT"]
        }
        with self.assertRaises(PermissionError) as ctx:
            update_document_metadata(
                user=emp_user,
                document_id=doc_id,
                document_title="Tampered Title",
                db_path=self.db_path
            )
        self.assertIn("Unauthorized", str(ctx.exception))

        # 2. Manager who owns the document (id 50) can update title and domain
        mgr_user = {
            "id": 50,
            "username": "mgr_user",
            "roles": ["MANAGER"],
            "permissions": ["document:read", "document:upload", "document:delete", "document:manage_permissions", "rag:query"],
            "departments": ["IT"]
        }
        # In test DB, domain 4 is IT
        updated_doc = update_document_metadata(
            user=mgr_user,
            document_id=doc_id,
            document_title="Approved IT Network Specification",
            domain_id=4,
            db_path=self.db_path
        )
        self.assertEqual(updated_doc["document_title"], "Approved IT Network Specification")
        self.assertEqual(updated_doc["domain_id"], 4)

        # 3. Manager without SUPER_ADMIN/ADMIN cannot escalate visibility to PUBLIC
        with self.assertRaises(PermissionError) as ctx:
            update_document_metadata(
                user=mgr_user,
                document_id=doc_id,
                visibility="PUBLIC",
                db_path=self.db_path
            )
        self.assertIn("Only administrators can set document visibility to PUBLIC", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

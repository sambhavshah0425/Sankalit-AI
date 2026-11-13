import json
import tempfile
import unittest
from pathlib import Path

from app.rag.vector_store import initialize_database
from app.security.audit import log_audit_event, query_audit_logs, sanitize_details
from app.services import auth_service


class TestAuditSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_audit.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_credential_redaction(self):
        sensitive_payload = {
            "username": "john_doe",
            "password": "SuperSecretPassword123!",
            "hashed_password": "$argon2id$v=19$m=65536,t=2,p=1$...",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "access_token": "secret_access_value",
            "refresh_token": "secret_refresh_value",
            "authorization": "Bearer secret_header",
            "metadata": {
                "department": "Engineering",
                "secret": "confidential_key"
            }
        }

        sanitized_json = sanitize_details(sensitive_payload)
        parsed = json.loads(sanitized_json)

        self.assertEqual(parsed["username"], "john_doe")
        self.assertEqual(parsed["password"], "[REDACTED]")
        self.assertEqual(parsed["hashed_password"], "[REDACTED]")
        self.assertEqual(parsed["token"], "[REDACTED]")
        self.assertEqual(parsed["access_token"], "[REDACTED]")
        self.assertEqual(parsed["refresh_token"], "[REDACTED]")
        self.assertEqual(parsed["authorization"], "[REDACTED]")
        self.assertEqual(parsed["metadata"]["secret"], "[REDACTED]")
        self.assertEqual(parsed["metadata"]["department"], "Engineering")

    def test_audit_event_logging_and_query(self):
        # 1. Register a user (triggers USER_REGISTER event)
        admin = auth_service.register_user(
            username="audit_admin",
            email="audit@sankalit.local",
            password="AdminPassword123",
            db_path=self.db_path
        )

        # 2. Login (triggers LOGIN_SUCCESS)
        _, _, r_token = auth_service.authenticate_user(
            username_or_email="audit_admin",
            password="AdminPassword123",
            db_path=self.db_path
        )

        # 3. Failed Login (triggers LOGIN_FAILED)
        try:
            auth_service.authenticate_user(
                username_or_email="audit_admin",
                password="WrongPassword123",
                db_path=self.db_path
            )
        except ValueError:
            pass

        # 4. Logout (triggers LOGOUT)
        auth_service.logout_user(
            raw_refresh_token=r_token,
            actor_id=admin["id"],
            actor_username="audit_admin",
            db_path=self.db_path
        )

        # Query all logs
        logs = query_audit_logs(limit=50, db_path=self.db_path)
        self.assertGreaterEqual(len(logs), 4)

        actions = [l["action"] for l in logs]
        self.assertIn("USER_REGISTER", actions)
        self.assertIn("LOGIN_SUCCESS", actions)
        self.assertIn("LOGIN_FAILED", actions)
        self.assertIn("LOGOUT", actions)

        # Query filtered by action
        login_logs = query_audit_logs(action="LOGIN_SUCCESS", db_path=self.db_path)
        self.assertEqual(len(login_logs), 1)
        self.assertEqual(login_logs[0]["actor_username"], "audit_admin")
        self.assertEqual(login_logs[0]["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()


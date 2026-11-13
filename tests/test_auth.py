import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path

import jwt

from app.config import JWT_SECRET_KEY, JWT_ALGORITHM
from app.rag.vector_store import initialize_database
from app.security.passwords import (
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    rotate_refresh_token,
    revoke_refresh_token,
)
from app.services import auth_service


class TestAuthSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_auth.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_argon2id_password_hashing(self):
        pw = "SecureSankalitPass2026!"
        hashed = hash_password(pw)

        # Ensure Argon2id prefix
        self.assertTrue(hashed.startswith("$argon2id$"))
        # Verify correct password
        self.assertTrue(verify_password(pw, hashed))
        # Verify incorrect password
        self.assertFalse(verify_password("WrongPassword123!", hashed))
        # Empty password checks
        self.assertFalse(verify_password("", hashed))
        self.assertFalse(verify_password(pw, ""))

    def test_password_strength_validation(self):
        valid, msg = validate_password_strength("Sankalit123")
        self.assertTrue(valid)
        self.assertIsNone(msg)

        # Too short
        valid, msg = validate_password_strength("Short1")
        self.assertFalse(valid)
        self.assertIn("at least 8 characters", msg)

        # No numbers
        valid, msg = validate_password_strength("NoNumbersHere")
        self.assertFalse(valid)
        self.assertIn("at least one number", msg)

        # No letters
        valid, msg = validate_password_strength("1234567890")
        self.assertFalse(valid)
        self.assertIn("at least one letter", msg)

    def test_jwt_lifecycle_and_validation(self):
        token = create_access_token(
            user_id=42,
            username="analyst_1",
            email="analyst@sankalit.local",
            roles=["EMPLOYEE"],
            expires_delta=timedelta(minutes=15)
        )
        self.assertIsInstance(token, str)

        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["username"], "analyst_1")
        self.assertEqual(payload["email"], "analyst@sankalit.local")
        self.assertEqual(payload["roles"], ["EMPLOYEE"])
        self.assertEqual(payload["type"], "access")

        # Expired token rejection
        expired_token = create_access_token(
            user_id=42,
            username="analyst_1",
            email="analyst@sankalit.local",
            roles=["EMPLOYEE"],
            expires_delta=timedelta(seconds=-1)
        )
        with self.assertRaises(jwt.ExpiredSignatureError):
            decode_access_token(expired_token)

        # Tampered / invalid token rejection
        tampered_token = token[:-5] + "XXXXX"
        with self.assertRaises(jwt.PyJWTError):
            decode_access_token(tampered_token)

    def test_user_registration_and_bootstrap_superadmin(self):
        # 1. First user registered in empty DB becomes SUPER_ADMIN
        admin_user = auth_service.register_user(
            username="root_admin",
            email="admin@sankalit.local",
            password="AdminPassword123",
            full_name="Root Admin",
            db_path=self.db_path
        )
        self.assertEqual(admin_user["username"], "root_admin")
        self.assertIn("SUPER_ADMIN", admin_user["roles"])
        self.assertTrue(admin_user["is_superuser"])

        # 2. Subsequent user registered by admin gets EMPLOYEE role
        employee = auth_service.register_user(
            username="staff_john",
            email="john@sankalit.local",
            password="StaffPassword123",
            full_name="John Doe",
            actor=admin_user,
            db_path=self.db_path
        )
        self.assertEqual(employee["username"], "staff_john")
        self.assertIn("EMPLOYEE", employee["roles"])
        self.assertFalse(employee["is_superuser"])

        # 3. Duplicate username or email rejection
        with self.assertRaises(ValueError) as ctx:
            auth_service.register_user(
                username="staff_john",
                email="different@sankalit.local",
                password="StaffPassword123",
                actor=admin_user,
                db_path=self.db_path
            )
        self.assertIn("already exists", str(ctx.exception))

    def test_login_and_brute_force_lockout(self):
        # Register test user
        user = auth_service.register_user(
            username="target_user",
            email="target@sankalit.local",
            password="CorrectPassword123",
            db_path=self.db_path
        )

        # Successful login
        u_data, a_token, r_token = auth_service.authenticate_user(
            username_or_email="target_user",
            password="CorrectPassword123",
            db_path=self.db_path
        )
        self.assertEqual(u_data["username"], "target_user")
        self.assertIsNotNone(a_token)
        self.assertIsNotNone(r_token)

        # 5 consecutive failed login attempts
        for _ in range(5):
            with self.assertRaises(ValueError):
                auth_service.authenticate_user(
                    username_or_email="target_user",
                    password="WrongPassword999",
                    db_path=self.db_path
                )

        # 6th attempt with CORRECT password must now be BLOCKED by lockout
        with self.assertRaises(PermissionError) as ctx:
            auth_service.authenticate_user(
                username_or_email="target_user",
                password="CorrectPassword123",
                db_path=self.db_path
            )
        self.assertIn("temporarily locked", str(ctx.exception).lower())

    def test_refresh_token_rotation_and_revocation(self):
        user = auth_service.register_user(
            username="rotation_user",
            email="rotation@sankalit.local",
            password="RotationPassword123",
            db_path=self.db_path
        )

        _, _, initial_refresh = auth_service.authenticate_user(
            username_or_email="rotation_user",
            password="RotationPassword123",
            db_path=self.db_path
        )

        # 1. Rotate refresh token
        new_access, second_refresh = auth_service.refresh_tokens(
            raw_refresh_token=initial_refresh,
            db_path=self.db_path
        )
        self.assertIsNotNone(new_access)
        self.assertNotEqual(initial_refresh, second_refresh)

        # 2. Replay attack: Old refresh token cannot be used again
        with self.assertRaises(ValueError) as ctx:
            auth_service.refresh_tokens(
                raw_refresh_token=initial_refresh,
                db_path=self.db_path
            )
        self.assertIn("revoked", str(ctx.exception).lower())

        # 3. Logout revokes active refresh token
        revoked = auth_service.logout_user(
            raw_refresh_token=second_refresh,
            actor_id=user["id"],
            db_path=self.db_path
        )
        self.assertTrue(revoked)

        # Subsequent refresh with revoked token fails
        with self.assertRaises(ValueError):
            auth_service.refresh_tokens(
                raw_refresh_token=second_refresh,
                db_path=self.db_path
            )

    def test_password_change_and_offline_admin_reset(self):
        admin = auth_service.register_user(
            username="super_admin",
            email="admin@corp.local",
            password="AdminPassword123",
            db_path=self.db_path
        )
        user = auth_service.register_user(
            username="alice",
            email="alice@corp.local",
            password="AliceOldPassword123",
            actor=admin,
            db_path=self.db_path
        )

        # User changes own password
        auth_service.change_password(
            user_id=user["id"],
            current_password="AliceOldPassword123",
            new_password="AliceNewPassword456",
            db_path=self.db_path
        )

        # Verify old password fails and new password succeeds
        with self.assertRaises(ValueError):
            auth_service.authenticate_user("alice", "AliceOldPassword123", db_path=self.db_path)

        u_data, _, _ = auth_service.authenticate_user("alice", "AliceNewPassword456", db_path=self.db_path)
        self.assertEqual(u_data["username"], "alice")

        # Admin offline reset
        auth_service.admin_reset_password(
            actor=admin,
            target_user_id=user["id"],
            new_password="AdminResetPass789",
            db_path=self.db_path
        )

        # Verify reset password works
        u_reset, _, _ = auth_service.authenticate_user("alice", "AdminResetPass789", db_path=self.db_path)
        self.assertEqual(u_reset["username"], "alice")


if __name__ == "__main__":
    unittest.main()


import tempfile
import unittest
from pathlib import Path

from app.rag.vector_store import initialize_database
from app.security.rbac import (
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_EMPLOYEE,
    ROLE_VIEWER,
    can_actor_manage_target_role,
    get_user_departments,
    get_user_permissions,
    get_user_roles,
    user_has_permission,
)
from app.services import auth_service, department_service, user_service


class TestRBAC(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_rbac.db"
        initialize_database(self.db_path)

        # 1. Root Super Admin (Bootstrap)
        self.super_admin = auth_service.register_user(
            username="root_admin",
            email="root@sankalit.local",
            password="RootPassword123",
            db_path=self.db_path
        )

        # 2. Delegated Admin
        self.admin = auth_service.register_user(
            username="dept_admin",
            email="admin@sankalit.local",
            password="AdminPassword123",
            requested_roles=[ROLE_ADMIN],
            actor=self.super_admin,
            db_path=self.db_path
        )

        # 3. Manager
        self.manager = auth_service.register_user(
            username="it_manager",
            email="manager@sankalit.local",
            password="ManagerPassword123",
            requested_roles=[ROLE_MANAGER],
            actor=self.admin,
            db_path=self.db_path
        )

        # 4. Normal Employee
        self.employee = auth_service.register_user(
            username="hr_employee",
            email="employee@sankalit.local",
            password="EmployeePassword123",
            requested_roles=[ROLE_EMPLOYEE],
            actor=self.admin,
            db_path=self.db_path
        )

        # 5. Viewer
        self.viewer = auth_service.register_user(
            username="auditor_viewer",
            email="viewer@sankalit.local",
            password="ViewerPassword123",
            requested_roles=[ROLE_VIEWER],
            actor=self.admin,
            db_path=self.db_path
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_role_and_permission_mappings(self):
        # Super Admin has all permissions
        sa_perms = get_user_permissions(self.super_admin["id"], db_path=self.db_path)
        self.assertIn("user:create", sa_perms)
        self.assertIn("user:delete", sa_perms)
        self.assertIn("role:manage", sa_perms)
        self.assertIn("audit:read", sa_perms)
        self.assertTrue(user_has_permission([ROLE_SUPER_ADMIN], sa_perms, "any:unregistered:perm"))

        # Admin has user management and audit:read, but not role:manage
        admin_perms = get_user_permissions(self.admin["id"], db_path=self.db_path)
        self.assertIn("user:create", admin_perms)
        self.assertIn("audit:read", admin_perms)
        self.assertNotIn("role:manage", admin_perms)

        # Manager has document upload & management, but not user:create
        manager_perms = get_user_permissions(self.manager["id"], db_path=self.db_path)
        self.assertIn("document:upload", manager_perms)
        self.assertIn("document:delete", manager_perms)
        self.assertNotIn("user:create", manager_perms)
        self.assertNotIn("audit:read", manager_perms)

        # Employee has query and read, but not upload or user management
        emp_perms = get_user_permissions(self.employee["id"], db_path=self.db_path)
        self.assertIn("rag:query", emp_perms)
        self.assertIn("document:read", emp_perms)
        self.assertNotIn("document:upload", emp_perms)
        self.assertNotIn("user:delete", emp_perms)

        # Viewer has only read and query
        viewer_perms = get_user_permissions(self.viewer["id"], db_path=self.db_path)
        self.assertIn("document:read", viewer_perms)
        self.assertNotIn("document:upload", viewer_perms)

    def test_privilege_escalation_prevention(self):
        # 1. Normal employee cannot assign themselves or anyone ADMIN or SUPER_ADMIN
        with self.assertRaises(PermissionError):
            auth_service.register_user(
                username="hacker_admin",
                email="hacker@sankalit.local",
                password="HackerPassword123",
                requested_roles=[ROLE_ADMIN],
                actor=self.employee,
                db_path=self.db_path
            )

        # 2. Manager cannot assign SUPER_ADMIN
        with self.assertRaises(PermissionError):
            auth_service.register_user(
                username="manager_elevated",
                email="elevated@sankalit.local",
                password="ElevatedPassword123",
                requested_roles=[ROLE_SUPER_ADMIN],
                actor=self.manager,
                db_path=self.db_path
            )

        # 3. Admin cannot promote anyone to SUPER_ADMIN
        with self.assertRaises(PermissionError):
            user_service.update_user(
                actor=self.admin,
                target_user_id=self.employee["id"],
                roles=[ROLE_SUPER_ADMIN],
                db_path=self.db_path
            )

        # 4. Admin cannot modify or deactivate SUPER_ADMIN
        with self.assertRaises(PermissionError):
            user_service.update_user(
                actor=self.admin,
                target_user_id=self.super_admin["id"],
                is_active=False,
                db_path=self.db_path
            )

        # 5. Sole SUPER_ADMIN cannot be deactivated or deleted
        with self.assertRaises(ValueError) as ctx:
            user_service.update_user(
                actor=self.super_admin,
                target_user_id=self.super_admin["id"],
                is_active=False,
                db_path=self.db_path
            )
        self.assertIn("sole Super Administrator", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            user_service.delete_user(
                actor=self.super_admin,
                target_user_id=self.super_admin["id"],
                db_path=self.db_path
            )
        self.assertIn("sole Super Administrator", str(ctx.exception))

    def test_department_management_and_multi_membership(self):
        # Initial departments exist from seeding
        all_depts = department_service.list_departments(db_path=self.db_path)
        dept_names = [d["name"] for d in all_depts]
        self.assertIn("HR", dept_names)
        self.assertIn("IT", dept_names)
        self.assertIn("Airport Systems", dept_names)
        self.assertIn("Acoustic / AV", dept_names)

        hr_dept = next(d for d in all_depts if d["name"] == "HR")
        it_dept = next(d for d in all_depts if d["name"] == "IT")

        # Assign employee to HR department
        department_service.assign_user_to_department(
            user_id=self.employee["id"],
            department_id=hr_dept["id"],
            is_primary=True,
            actor=self.super_admin,
            db_path=self.db_path
        )

        # Assign employee also to IT department (multi-department membership)
        department_service.assign_user_to_department(
            user_id=self.employee["id"],
            department_id=it_dept["id"],
            is_primary=False,
            actor=self.super_admin,
            db_path=self.db_path
        )

        user_depts = get_user_departments(self.employee["id"], db_path=self.db_path)
        self.assertEqual(len(user_depts), 2)
        assigned_dept_ids = {d["id"] for d in user_depts}
        self.assertIn(hr_dept["id"], assigned_dept_ids)
        self.assertIn(it_dept["id"], assigned_dept_ids)

        # Create custom department
        new_dept = department_service.create_department(
            name="Cybersecurity & Forensics",
            code="CYBER",
            description="Enterprise security division",
            actor=self.super_admin,
            db_path=self.db_path
        )
        self.assertEqual(new_dept["code"], "CYBER")


if __name__ == "__main__":
    unittest.main()


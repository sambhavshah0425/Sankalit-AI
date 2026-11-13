import logging
import sqlite3
from pathlib import Path
from typing import Optional

from app.config import DATABASE_PATH
from app.rag.vector_store import get_db

logger = logging.getLogger(__name__)

INITIAL_DEPARTMENTS = [
    ("HR", "HR", "Human Resources department"),
    ("IT", "IT", "Information Technology and systems"),
    ("Acoustic / AV", "AV", "Acoustics and Audio-Visual engineering"),
    ("Airport Systems", "AIRPORT", "Airport Systems and infrastructure"),
    ("Lighting", "LIGHT", "Lighting design and engineering"),
    ("MEP", "MEP", "Mechanical, Electrical, and Plumbing engineering"),
    ("Management", "MGMT", "Executive and Management"),
    ("General Administration", "ADMIN_GEN", "General Administration and corporate services"),
]

INITIAL_PERMISSIONS = [
    ("user:read", "View user accounts and profiles"),
    ("user:create", "Create new user accounts"),
    ("user:update", "Modify existing user accounts"),
    ("user:delete", "Deactivate or delete user accounts"),
    ("role:read", "View roles and assigned permissions"),
    ("role:assign", "Assign roles to users"),
    ("role:manage", "Create and modify roles"),
    ("department:read", "View departments and rosters"),
    ("department:manage", "Manage departments and assign user memberships"),
    ("document:read", "Read and view authorized documents"),
    ("document:upload", "Upload new documents to knowledge base"),
    ("document:delete", "Delete authorized documents"),
    ("document:manage_permissions", "Modify document access permissions"),
    ("rag:query", "Perform semantic queries against authorized knowledge base"),
    ("audit:read", "View security and compliance audit logs"),
    ("system:config", "View and update system configuration"),
    ("taxonomy:read", "View knowledge domains and categories"),
    ("taxonomy:manage", "Create, update, or deactivate knowledge domains and categories"),
    ("classification:manage", "Review, edit, and approve document classifications"),
    ("company_profile:update", "Update official company profile and identity information"),
]

ROLE_PERMISSION_MAP = {
    "SUPER_ADMIN": [p[0] for p in INITIAL_PERMISSIONS],  # All permissions
    "ADMIN": [
        "user:read", "user:create", "user:update", "user:delete",
        "role:read", "role:assign",
        "department:read", "department:manage",
        "document:read", "document:upload", "document:delete", "document:manage_permissions",
        "rag:query", "audit:read",
        "taxonomy:read", "taxonomy:manage", "classification:manage", "company_profile:update"
    ],
    "MANAGER": [
        "user:read",
        "department:read",
        "document:read", "document:upload", "document:delete", "document:manage_permissions",
        "rag:query",
        "taxonomy:read", "classification:manage"
    ],
    "EMPLOYEE": [
        "user:read",
        "department:read",
        "document:read",
        "rag:query",
        "taxonomy:read"
    ],
    "VIEWER": [
        "document:read",
        "rag:query",
        "taxonomy:read"
    ]
}

INITIAL_KNOWLEDGE_DOMAINS = [
    ("Company Profile", "company-profile", "Company overview, history, mission, vision, and core capabilities"),
    ("Acoustic", "acoustic", "Architectural acoustics, noise & vibration control, sound isolation, and auditorium design"),
    ("Airport Systems", "airport-systems", "Airport technology, operational systems, BHS, AODB, and integration"),
    ("IT", "it", "Information technology infrastructure, networking, cybersecurity, and enterprise systems"),
    ("Lighting", "lighting", "Architectural lighting design, lighting control systems, and technical specifications"),
    ("MEP", "mep", "Mechanical, electrical, plumbing, fire protection, and building services engineering"),
    ("HR", "hr", "Employee policies, onboarding, benefits, leave, performance, and internal HR guidelines"),
    ("Projects", "projects", "Project documentation, proposals, technical submissions, BOQs, and progress reports"),
    ("Operations and Administration", "operations", "Standard operating procedures (SOPs), procurement, and administrative workflows"),
    ("Management", "management", "Executive management, strategic planning, organizational governance, and policies"),
]

INITIAL_KNOWLEDGE_CATEGORIES = {
    "company-profile": [
        ("Overview & History", "overview-history", "Company background, founding, and history"),
        ("Mission & Vision", "mission-vision", "Organizational mission, vision, and core values"),
        ("Organizational Structure", "org-structure", "Departments, leadership, and operational hierarchy"),
        ("Services & Capabilities", "services-capabilities", "Consulting services and domain expertise"),
        ("Company Terminology", "terminology", "Official terminology, acronyms, and glossaries"),
    ],
    "acoustic": [
        ("Architectural Acoustics", "architectural-acoustics", "Room acoustics, reverberation, and space tuning"),
        ("Noise & Vibration Control", "noise-vibration", "Environmental and industrial noise mitigation"),
        ("Sound Isolation", "sound-isolation", "Partition design and sound transmission loss"),
        ("Auditorium Design", "auditorium-design", "Theatres, concert halls, and auditorium acoustics"),
        ("AV Integration", "av-integration", "Audio-visual and acoustic system integration"),
        ("Technical Specifications", "technical-specs", "Acoustic materials and testing specifications"),
    ],
    "airport-systems": [
        ("Airport IT & Networks", "airport-it-networks", "Airport enterprise communications and network backbones"),
        ("BHS & Baggage Technology", "bhs-baggage", "Baggage handling systems and tracking"),
        ("AODB & Airport Operations", "aodb-operations", "Airport Operational Database, RMS, and FIDS"),
        ("Security & Access Systems", "security-access", "Access control, CCTV, and passenger screening tech"),
        ("System Integration", "system-integration", "Master system integration across airport subsystems"),
    ],
    "it": [
        ("IT Infrastructure", "infrastructure", "Server, virtualization, storage, and cloud infrastructure"),
        ("Networking & Telecommunications", "networking", "LAN, WAN, wireless, and structured cabling"),
        ("Cybersecurity & Data Protection", "cybersecurity", "Security policies, firewalling, and encryption"),
        ("Enterprise Software & Tools", "enterprise-software", "Internal software, productivity tools, and licenses"),
        ("Support Procedures", "support-procedures", "Helpdesk workflows, troubleshooting, and maintenance"),
    ],
    "lighting": [
        ("Architectural Lighting Design", "architectural-lighting", "Indoor lighting concepts, lux levels, and aesthetics"),
        ("Lighting Control Systems", "lighting-controls", "DALI, DMX, sensors, and centralized lighting automation"),
        ("Façade & Landscape Lighting", "facade-landscape", "Exterior, landscape, and architectural façade illumination"),
        ("Lighting Specifications & BOQs", "lighting-specs", "Fixture schedules, datasheets, and bill of quantities"),
    ],
    "mep": [
        ("HVAC & Mechanical Systems", "hvac-mechanical", "Heating, ventilation, air conditioning, and ductwork"),
        ("Electrical Distribution & Power", "electrical-power", "Substations, transformers, panels, and emergency power"),
        ("Plumbing & Public Health", "plumbing-sanitary", "Water supply, drainage, sanitary, and rainwater harvesting"),
        ("Fire Protection & Life Safety", "fire-safety", "Sprinklers, fire alarms, suppression, and smoke management"),
        ("BIM Coordination & Drawings", "bim-coordination", "Revit MEP models, clash detection, and coordination drawings"),
    ],
    "hr": [
        ("Employee Handbook", "employee-handbook", "General employee conduct, working hours, and guidelines"),
        ("Onboarding & Orientation", "onboarding", "New hire onboarding notes, checklists, and introductions"),
        ("Leave & Attendance Policies", "leave-attendance", "Annual leave, sick leave, public holidays, and working time"),
        ("Compensation & Benefits", "compensation-benefits", "Salary structures, bonuses, health insurance, and perks"),
        ("Performance Appraisals", "performance-appraisals", "Goal setting, quarterly reviews, and evaluation criteria"),
        ("Grievance & Conduct", "grievance-conduct", "Disciplinary procedures, POSH, and grievance escalation"),
    ],
    "projects": [
        ("Project Proposals & Bids", "proposals-bids", "RFPs, technical proposals, and commercial bids"),
        ("Technical Submissions", "technical-submissions", "Design basis reports (DBR) and technical specifications"),
        ("Bills of Quantities (BOQs)", "boqs", "Cost estimates, schedules of rates, and BOQ sheets"),
        ("Project Progress Reports", "progress-reports", "Milestone reports, site inspection notes, and minutes"),
        ("Client Correspondence", "client-correspondence", "Letters, transmittals, and client approvals"),
        ("As-Built Documentation", "as-built", "Handover records, as-built drawings, and closeout manuals"),
    ],
    "operations": [
        ("Standard Operating Procedures (SOPs)", "sops", "Documented operational procedures and checklists"),
        ("Procurement & Vendor Management", "procurement", "Vendor registration, purchase orders, and supplier reviews"),
        ("Internal Coordination & Meetings", "internal-coordination", "Inter-department coordination and review schedules"),
        ("Document Control & Archiving", "document-control", "Numbering standards, filing rules, and version management"),
    ],
    "management": [
        ("Strategic Planning", "strategic-planning", "Annual goals, business strategy, and roadmap documents"),
        ("Management Reports", "management-reports", "Quarterly operational summaries and executive briefings"),
        ("Organizational Policies", "organizational-policies", "Board-approved policies and company governance"),
        ("Risk & Quality Management", "risk-quality", "ISO certifications, quality manual, and risk registers"),
    ],
}


def migrate_database_schema(db_path: Optional[Path] = None) -> None:
    """
    Run non-destructive schema migrations on the SQLite database:
    1. Upgrade existing `documents` table with security and knowledge metadata.
    2. Create security, RBAC, department, token, and audit tables.
    3. Create knowledge taxonomy tables (knowledge_domains, knowledge_categories, company_profile).
    4. Create database-level immutability triggers for audit logs.
    5. Seed default roles, permissions, departments, knowledge taxonomy, and company profile.
    """
    with get_db(db_path) as conn:
        # Step 1: Ensure existing documents table has security & taxonomy metadata columns
        cursor = conn.execute("PRAGMA table_info(documents)")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        if existing_cols:
            # Milestone 2 security columns
            if "owner_id" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN owner_id INTEGER REFERENCES users(id)")
            if "visibility" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN visibility TEXT NOT NULL DEFAULT 'COMPANY'")
            if "access_policy" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN access_policy TEXT")
            if "status" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

            # Milestone 3 knowledge taxonomy & metadata columns
            if "document_title" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN document_title TEXT")
            if "domain_id" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN domain_id INTEGER REFERENCES knowledge_domains(id) ON DELETE SET NULL")
            if "category_id" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN category_id INTEGER REFERENCES knowledge_categories(id) ON DELETE SET NULL")
            if "project_name" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN project_name TEXT")
            if "project_identifier" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN project_identifier TEXT")
            if "document_type" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN document_type TEXT DEFAULT 'general'")
            if "document_date" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN document_date TEXT")
            if "document_version" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN document_version TEXT DEFAULT '1.0'")
            if "confidentiality_level" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN confidentiality_level TEXT DEFAULT 'INTERNAL'")
            if "classification_status" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN classification_status TEXT DEFAULT 'UNCLASSIFIED'")
            if "classification_confidence" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN classification_confidence REAL DEFAULT 0.0")
            if "classification_explanation" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN classification_explanation TEXT")
            if "updated_at" not in existing_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        # Step 2: Create users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                full_name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_superuser INTEGER NOT NULL DEFAULT 0,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

        # Step 3: Create roles table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_system INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Step 4: Create permissions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """)

        # Step 5: Role-Permissions junction
        conn.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                PRIMARY KEY (role_id, permission_id),
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
            )
        """)

        # Step 6: User-Roles junction
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, role_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
            )
        """)

        # Step 7: Departments table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Step 8: User-Departments junction
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_departments (
                user_id INTEGER NOT NULL,
                department_id INTEGER NOT NULL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, department_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
            )
        """)

        # Step 9: Document-Departments junction
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_departments (
                document_id INTEGER NOT NULL,
                department_id INTEGER NOT NULL,
                PRIMARY KEY (document_id, department_id),
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_dept ON document_departments(document_id, department_id)")

        # Step 10: Document explicit permissions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                user_id INTEGER,
                role_id INTEGER,
                permission_type TEXT NOT NULL DEFAULT 'read',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                CHECK (user_id IS NOT NULL OR role_id IS NOT NULL)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_perm_doc ON document_permissions(document_id)")

        # Step 11: Refresh tokens table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_token_hash ON refresh_tokens(token_hash)")

        # Step 12: Audit logs table & immutability triggers
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                actor_username TEXT,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                status TEXT NOT NULL DEFAULT 'SUCCESS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(created_at)")

        # Database-level immutability triggers: prevent modification or deletion of audit logs
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_audit_log_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit log records are immutable and cannot be updated.');
            END;
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_audit_log_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit log records are immutable and cannot be deleted.');
            END;
        """)

        # Step 13: Knowledge Domains table (Milestone 3)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_domains_slug ON knowledge_domains(slug)")

        # Step 14: Knowledge Categories table (Milestone 3)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER NOT NULL REFERENCES knowledge_domains(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(domain_id, slug)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_categories_domain ON knowledge_categories(domain_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_categories_slug ON knowledge_categories(slug)")

        # Step 15: Company Profile table (Milestone 3)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS company_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                company_description TEXT,
                mission TEXT,
                vision TEXT,
                official_website TEXT,
                contact_information TEXT,
                additional_information_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Metadata indexes on documents table
        if existing_cols:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_domain ON documents(domain_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_category ON documents(category_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_project ON documents(project_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_type ON documents(document_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_class_status ON documents(classification_status)")

        # Step 16: Seed Departments
        for name, code, desc in INITIAL_DEPARTMENTS:
            conn.execute(
                "INSERT OR IGNORE INTO departments (name, code, description) VALUES (?, ?, ?)",
                (name, code, desc)
            )

        # Step 17: Seed Permissions
        for perm_name, perm_desc in INITIAL_PERMISSIONS:
            conn.execute(
                "INSERT OR IGNORE INTO permissions (name, description) VALUES (?, ?)",
                (perm_name, perm_desc)
            )

        # Step 18: Seed Roles & Role Permissions
        for role_name, perms in ROLE_PERMISSION_MAP.items():
            conn.execute(
                "INSERT OR IGNORE INTO roles (name, description, is_system) VALUES (?, ?, 1)",
                (role_name, f"System built-in role: {role_name}")
            )
            role_row = conn.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
            if role_row:
                role_id = role_row["id"]
                for perm in perms:
                    p_row = conn.execute("SELECT id FROM permissions WHERE name = ?", (perm,)).fetchone()
                    if p_row:
                        conn.execute(
                            "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                            (role_id, p_row["id"])
                        )

        # Step 19: Seed Knowledge Domains (Milestone 3)
        for dom_name, dom_slug, dom_desc in INITIAL_KNOWLEDGE_DOMAINS:
            conn.execute(
                "INSERT OR IGNORE INTO knowledge_domains (name, slug, description) VALUES (?, ?, ?)",
                (dom_name, dom_slug, dom_desc)
            )

        # Step 20: Seed Knowledge Categories (Milestone 3)
        for dom_slug, categories in INITIAL_KNOWLEDGE_CATEGORIES.items():
            dom_row = conn.execute("SELECT id FROM knowledge_domains WHERE slug = ?", (dom_slug,)).fetchone()
            if dom_row:
                domain_id = dom_row["id"]
                for cat_name, cat_slug, cat_desc in categories:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO knowledge_categories (domain_id, name, slug, description)
                        VALUES (?, ?, ?, ?)
                        """,
                        (domain_id, cat_name, cat_slug, cat_desc)
                    )

        # Step 21: Seed Default Company Profile (Milestone 3)
        profile_count = conn.execute("SELECT COUNT(*) FROM company_profile").fetchone()[0]
        if profile_count == 0:
            conn.execute(
                """
                INSERT INTO company_profile (
                    company_name, company_description, mission, vision,
                    official_website, contact_information, additional_information_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Sankalit Consultant",
                    "Sankalit Consultant is a multidisciplinary engineering and consulting consultancy firm specializing in Acoustics, Audio-Visual Systems, Airport Systems, Architectural Lighting, Mechanical, Electrical, Plumbing (MEP), and Information Technology infrastructure design.",
                    "Delivering state-of-the-art engineering consultancy and intelligent infrastructure design with precision, innovation, and technological excellence.",
                    "To be a premier multidisciplinary engineering consultancy recognized globally for transformative infrastructure, technological integration, and sustainable design.",
                    "https://sankalit.com",
                    "info@sankalit.com",
                    '{"established": "Consulting Practice", "headquarters": "India", "practice_areas": ["Acoustics", "Airport Systems", "IT", "Lighting", "MEP", "Audio-Visual"]}'
                )
            )

        conn.commit()
        logger.info("Database security & knowledge taxonomy schema migrated and seeded successfully.")

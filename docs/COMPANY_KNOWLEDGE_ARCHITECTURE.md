# SANKALIT INTELLIGENCE — COMPANY KNOWLEDGE ARCHITECTURE

## 1. Architectural Overview

The Milestone 3 Company Knowledge Architecture elevates Sankalit Intelligence from an unstructured document search bot into an organized, domain-aware enterprise repository.

```
+---------------------------------------------------------------------------------------------------+
|                                     KNOWLEDGE TAXONOMY HIERARCHY                                  |
+---------------------------------------------------------------------------------------------------+
|  1. Company Profile           (Overview, Mission, Organization, Services, Terminology)            |
|  2. Acoustic                  (Architectural Acoustics, Noise/Vibration, Sound Isolation, AV)     |
|  3. Airport Systems           (IT & Networks, BHS, AODB, Security & Access, System Integration)   |
|  4. IT                        (Infrastructure, Networking, Cybersecurity, Software, Support)      |
|  5. Lighting                  (Architectural Lighting, Control Systems, Technical Specs)          |
|  6. MEP                       (HVAC & Mechanical, Electrical & Power, Plumbing, Fire Protection)  |
|  7. HR                        (Policies & Handbook, Onboarding, Compensation, Grievance, Leave)   |
|  8. Projects                  (Proposals & RFPs, BOQs, Client Submissions, Progress Reports)      |
|  9. Operations & Admin        (SOPs, Procurement, Internal Coordination, Document Control)        |
| 10. Management                (Strategic Planning, Management Reports, Governance, Risk/ISO)      |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Knowledge Taxonomy (10 Initial Domains & 50 Categories)

### 1. Company Profile (`company-profile`)
- **Overview & History** (`overview-history`)
- **Mission & Vision** (`mission-vision`)
- **Organizational Structure** (`org-structure`)
- **Services & Capabilities** (`services-capabilities`)
- **Company Terminology** (`terminology`)

### 2. Acoustic (`acoustic`)
- **Architectural Acoustics** (`architectural-acoustics`)
- **Noise & Vibration Control** (`noise-vibration`)
- **Sound Isolation** (`sound-isolation`)
- **Auditorium Design** (`auditorium-design`)
- **AV Integration** (`av-integration`)
- **Technical Specifications** (`technical-specs`)

### 3. Airport Systems (`airport-systems`)
- **Airport IT & Networks** (`airport-it-networks`)
- **BHS & Baggage Technology** (`bhs-baggage`)
- **AODB & Airport Operations** (`aodb-operations`)
- **Security & Access Systems** (`security-access`)
- **System Integration** (`system-integration`)

### 4. IT (`it`)
- **IT Infrastructure** (`infrastructure`)
- **Networking & Telecommunications** (`networking`)
- **Cybersecurity & Data Protection** (`cybersecurity`)
- **Enterprise Software & Tools** (`enterprise-software`)
- **Support Procedures** (`support-procedures`)

### 5. Lighting (`lighting`)
- **Architectural Lighting Design** (`architectural-lighting`)
- **Lighting Controls & Automation** (`lighting-controls`)
- **Daylighting & Sustainability** (`daylighting`)
- **Technical Specifications & BOQs** (`lighting-specs`)
- **Calculations & Simulations** (`lighting-calculations`)

### 6. MEP (`mep`)
- **HVAC & Thermal Systems** (`hvac`)
- **Electrical & Power Distribution** (`electrical`)
- **Plumbing & Public Health Engineering** (`plumbing`)
- **Fire Life Safety & Suppression** (`fire-safety`)
- **BIM & Engineering Coordination** (`bim-coordination`)

### 7. HR (`hr`)
- **Policies & Handbook** (`policies-handbook`)
- **Onboarding & Induction** (`onboarding`)
- **Performance & Appraisals** (`performance-appraisals`)
- **Benefits & Compensation** (`compensation-benefits`)
- **Grievance & Redressal** (`grievance-redressal`)
- **Leave & Attendance** (`leave-attendance`)

### 8. Projects (`projects`)
- **Technical Proposals & Bids** (`proposals-bids`)
- **Design Basis Reports (DBR)** (`dbr`)
- **Bill of Quantities (BOQ)** (`boq`)
- **Project Progress Reports** (`progress-reports`)
- **Client Deliverables & Minutes** (`client-deliverables`)

### 9. Operations and Administration (`operations`)
- **Standard Operating Procedures (SOP)** (`sop`)
- **Procurement & Vendor Management** (`procurement`)
- **Internal Coordination & Meetings** (`internal-coordination`)
- **Document Control & Archiving** (`document-control`)

### 10. Management (`management`)
- **Strategic Planning** (`strategic-planning`)
- **Management Reports** (`management-reports`)
- **Organizational Policies** (`organizational-policies`)
- **Risk & Quality Management** (`risk-quality`)

---

## 3. Database Schema Extensions

### `knowledge_domains` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique domain ID |
| `name` | TEXT | NOT NULL UNIQUE | Human-readable name |
| `slug` | TEXT | NOT NULL UNIQUE | URL/lookup slug |
| `description` | TEXT | | Detailed domain scope |
| `is_active` | INTEGER | NOT NULL DEFAULT 1 | Soft-deletion flag |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update timestamp |

### `knowledge_categories` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique category ID |
| `domain_id` | INTEGER | NOT NULL REFERENCES knowledge_domains(id) | Parent domain |
| `name` | TEXT | NOT NULL | Subcategory name |
| `slug` | TEXT | NOT NULL | Subcategory slug |
| `description` | TEXT | | Subcategory description |
| `is_active` | INTEGER | NOT NULL DEFAULT 1 | Soft-deletion flag |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update timestamp |

### `company_profile` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY CHECK(id = 1) | Single authoritative record |
| `company_name` | TEXT | NOT NULL | Official company name |
| `company_description` | TEXT | NOT NULL | Corporate overview |
| `mission` | TEXT | | Mission statement |
| `vision` | TEXT | | Vision statement |
| `official_website` | TEXT | | Corporate website URL |
| `contact_information` | TEXT | | Primary contact email/phone |
| `additional_information_json` | TEXT | | Practice areas, office locations, etc. |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last modified |

### Extended Metadata on `documents` Table
- `document_title`: Human-readable document title.
- `domain_id`: Foreign key referencing `knowledge_domains(id)`.
- `category_id`: Foreign key referencing `knowledge_categories(id)`.
- `project_name`: Project name (e.g. "Project Horizon").
- `project_identifier`: Project code (e.g. "PRJ-2026-001").
- `document_type`: Type (`policy`, `specification`, `proposal`, `report`, `sop`, `drawing`, `general`).
- `document_date`: Publication date (`YYYY-MM-DD`).
- `document_version`: Version string (e.g. `1.0`).
- `confidentiality_level`: Confidentiality tier (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`).
- `classification_status`: Workflow state (`CLASSIFIED`, `NEEDS_REVIEW`, `UNCLASSIFIED`).
- `classification_confidence`: Heuristic confidence score (`0.0` to `1.0`).
- `classification_explanation`: Reasoning string explaining why the document was placed in this domain.
- `updated_at`: Metadata update timestamp.

---

## 4. Intelligent Ingestion & Classification Service

Implemented in `app/services/classification_service.py`:
1. **Lightweight Rule-Based Heuristics**: Evaluates title, filename, and extracted text for domain-specific technical vocabulary.
2. **Confidence Scoring**:
   - `confidence >= 0.65`: Automatically marked as `CLASSIFIED`.
   - `0.35 <= confidence < 0.65`: Marked as `NEEDS_REVIEW` (added to administrative review queue).
   - `confidence < 0.35`: Marked as `UNCLASSIFIED`.
3. **Approval Workflow**:
   - Authorized managers and administrators can inspect pending classifications via `GET /knowledge/classification/pending`.
   - They can review details via `GET /knowledge/classification/{id}`.
   - They can adjust fields via `PUT /knowledge/classification/{id}`.
   - They can approve via `POST /knowledge/classification/{id}/approve`.
   - They can re-run automated heuristics via `POST /knowledge/classification/{id}/reclassify`.


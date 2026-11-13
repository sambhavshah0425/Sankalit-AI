"""Tests for Knowledge Taxonomy Services:
Domains, categories, company profile, and authorized statistics.
"""

import tempfile
import unittest
from pathlib import Path

from app.rag.vector_store import initialize_database
from app.services.taxonomy_service import (
    create_knowledge_category,
    create_knowledge_domain,
    deactivate_knowledge_category,
    deactivate_knowledge_domain,
    get_knowledge_category,
    get_knowledge_domain,
    get_knowledge_domain_by_slug,
    get_taxonomy_statistics,
    list_knowledge_categories,
    list_knowledge_domains,
    update_company_profile,
    update_knowledge_category,
    update_knowledge_domain,
)


class TestKnowledgeTaxonomy(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_taxonomy.db"
        initialize_database(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_seeded_domains_and_categories(self):
        """Verify the 10 initial domains and subcategories are seeded properly."""
        domains = list_knowledge_domains(db_path=self.db_path)
        self.assertEqual(len(domains), 10)

        domain_slugs = {d["slug"] for d in domains}
        expected_slugs = {
            "company-profile", "acoustic", "airport-systems", "it",
            "lighting", "mep", "hr", "projects", "operations", "management"
        }
        self.assertEqual(domain_slugs, expected_slugs)

        # Check categories under 'acoustic'
        acoustic_dom = get_knowledge_domain_by_slug("acoustic", db_path=self.db_path)
        self.assertIsNotNone(acoustic_dom)
        cats = list_knowledge_categories(domain_id=acoustic_dom["id"], db_path=self.db_path)
        self.assertTrue(len(cats) >= 5)

    def test_domain_crud(self):
        """Test domain creation, retrieval, update, and deactivation."""
        new_dom = create_knowledge_domain(
            name="Environmental & Sustainability",
            slug="sustainability",
            description="Green building certifications, LEED, and ESG",
            db_path=self.db_path
        )
        self.assertEqual(new_dom["name"], "Environmental & Sustainability")
        self.assertEqual(new_dom["slug"], "sustainability")

        # Update
        updated = update_knowledge_domain(
            domain_id=new_dom["id"],
            description="Updated description for ESG",
            db_path=self.db_path
        )
        self.assertEqual(updated["description"], "Updated description for ESG")

        # Deactivate
        deactivate_knowledge_domain(new_dom["id"], db_path=self.db_path)
        active_domains = list_knowledge_domains(include_inactive=False, db_path=self.db_path)
        self.assertNotIn("sustainability", {d["slug"] for d in active_domains})

    def test_category_crud(self):
        """Test category creation, update, and deactivation."""
        hr_dom = get_knowledge_domain_by_slug("hr", db_path=self.db_path)
        new_cat = create_knowledge_category(
            domain_id=hr_dom["id"],
            name="Remote Work Guidelines",
            slug="remote-work",
            description="Work from home guidelines and policies",
            db_path=self.db_path
        )
        self.assertEqual(new_cat["name"], "Remote Work Guidelines")

        # Retrieve
        cat = get_knowledge_category(new_cat["id"], db_path=self.db_path)
        self.assertEqual(cat["domain_slug"], "hr")

        # Deactivate
        deactivate_knowledge_category(new_cat["id"], db_path=self.db_path)
        cats = list_knowledge_categories(domain_id=hr_dom["id"], include_inactive=False, db_path=self.db_path)
        self.assertNotIn("remote-work", {c["slug"] for c in cats})

    def test_company_profile_update(self):
        """Test company profile update."""
        updated = update_company_profile(
            company_name="Sankalit Consultant LLP",
            mission="Redefining global engineering excellence through technology.",
            db_path=self.db_path
        )
        self.assertEqual(updated["company_name"], "Sankalit Consultant LLP")
        self.assertIn("Redefining global engineering", updated["mission"])

    def test_taxonomy_statistics_authorization_filtering(self):
        """Verify taxonomy statistics filter strictly to allowed_document_ids."""
        # Empty allowed_document_ids returns 0 documents without metadata leakage
        stats_empty = get_taxonomy_statistics(allowed_document_ids=[], db_path=self.db_path)
        self.assertEqual(stats_empty["total_documents"], 0)
        self.assertEqual(stats_empty["total_chunks"], 0)


if __name__ == "__main__":
    unittest.main()

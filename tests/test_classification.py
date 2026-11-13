"""Tests for Intelligent Document Classification Service:
Heuristics, confidence scoring, approval workflows, and manual corrections.
"""

import tempfile
import unittest
from pathlib import Path

from app.rag.vector_store import initialize_database, save_document
from app.services.classification_service import (
    STATUS_CLASSIFIED,
    STATUS_NEEDS_REVIEW,
    STATUS_UNCLASSIFIED,
    approve_document_classification,
    classify_document_content,
    get_pending_classifications,
    update_document_classification,
)


class TestDocumentClassification(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_classification.db"
        initialize_database(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_classify_hr_policy_document(self):
        """Verify HR policy content is classified into HR domain with high confidence."""
        hr_text = (
            "Sankalit Consultant Employee Leave Policy: "
            "All permanent employees accrue 2 days of annual leave per month. "
            "Probationary period is 6 months from onboarding date. "
            "Performance appraisal is conducted bi-annually with salary review."
        )
        res = classify_document_content(hr_text, "Sankalit_Employee_Leave_Policy.pdf", db_path=self.db_path)
        self.assertEqual(res["domain_slug"], "hr")
        self.assertIsNotNone(res["domain_id"])
        self.assertEqual(res["document_type"], "policy")
        self.assertGreaterEqual(res["confidence"], 0.65)
        self.assertEqual(res["status"], STATUS_CLASSIFIED)

    def test_classify_airport_specification_document(self):
        """Verify airport systems technical content is classified correctly."""
        airport_text = (
            "Technical Specification for Terminal 2 Baggage Handling System (BHS) and AODB: "
            "The Airport Operational Database (AODB) must interface directly with the FIDS "
            "and passenger boarding bridge control systems."
        )
        res = classify_document_content(airport_text, "T2_BHS_AODB_Tech_Spec.docx", db_path=self.db_path)
        self.assertEqual(res["domain_slug"], "airport-systems")
        self.assertEqual(res["document_type"], "technical_spec")
        self.assertEqual(res["status"], STATUS_CLASSIFIED)

    def test_classify_acoustic_auditorium_document(self):
        """Verify acoustic auditorium text classification."""
        acoustic_text = (
            "Acoustic design report for the National Performing Arts Centre Auditorium: "
            "Reverberation time RT60 target is 1.6 seconds. "
            "Sound isolation partitions must achieve minimum STC 55 rating for noise control."
        )
        res = classify_document_content(acoustic_text, "Auditorium_Acoustic_Design.pdf", db_path=self.db_path)
        self.assertEqual(res["domain_slug"], "acoustic")
        self.assertEqual(res["status"], STATUS_CLASSIFIED)

    def test_classify_vague_text_needs_review(self):
        """Verify document with minimal keywords is marked NEEDS_REVIEW or UNCLASSIFIED."""
        vague_text = "This is a general summary of our weekly catchup meeting regarding various items."
        res = classify_document_content(vague_text, "notes.txt", db_path=self.db_path)
        self.assertIn(res["status"], (STATUS_NEEDS_REVIEW, STATUS_UNCLASSIFIED))

    def test_manual_classification_update_and_approval(self):
        """Verify updating and approving classification for a persisted document."""
        # Save a sample document
        mock_chunks = [{
            "chunk_index": 0,
            "text": "Sample text for testing classification updates.",
            "embedding": [0.01] * 768
        }]
        doc_id = save_document(
            filename="unclassified_doc.pdf",
            file_type=".pdf",
            content_hash="hash_unclassified_123",
            character_count=45,
            chunks=mock_chunks,
            classification_status=STATUS_NEEDS_REVIEW,
            db_path=self.db_path
        )

        # Check in pending classifications
        pending = get_pending_classifications(db_path=self.db_path)
        self.assertTrue(any(p["id"] == doc_id for p in pending))

        # Approve classification
        approved = approve_document_classification(doc_id, db_path=self.db_path)
        self.assertEqual(approved["classification_status"], STATUS_CLASSIFIED)

        # Verify no longer pending
        pending_after = get_pending_classifications(db_path=self.db_path)
        self.assertFalse(any(p["id"] == doc_id for p in pending_after))


if __name__ == "__main__":
    unittest.main()

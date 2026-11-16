from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.claims.models import Claim, ClaimDocument, ClaimNarrative, ClaimSummary

User = get_user_model()


class ClaimModelTests(TestCase):
    def setUp(self):
        self.adjuster = User.objects.create_user(
            email="adjuster@test.com", password="Password123!", role=User.Role.ADJUSTER
        )

    def test_claim_defaults_to_submitted_status(self):
        claim = Claim.objects.create(
            claimant_name="Jane Doe",
            policy_number="POL-TEST-1",
            claim_type=Claim.ClaimType.AUTO,
            submitted_by=self.adjuster,
        )
        self.assertEqual(claim.status, Claim.Status.SUBMITTED)
        self.assertIn("Jane Doe", str(claim))

    def test_claim_document_relation(self):
        claim = Claim.objects.create(
            claimant_name="Jane Doe",
            policy_number="POL-TEST-2",
            claim_type=Claim.ClaimType.PROPERTY,
            submitted_by=self.adjuster,
        )
        doc = ClaimDocument.objects.create(
            claim=claim,
            document_type=ClaimDocument.DocumentType.INVOICE,
            blob_path="blob_stub/x/y.txt",
            extracted_fields={"vendor": "Acme", "amount": 10.0, "date": "2024-01-01"},
        )
        self.assertEqual(claim.documents.count(), 1)
        self.assertEqual(doc.extracted_fields["vendor"], "Acme")

    def test_claim_narrative_unique_search_doc_id(self):
        claim = Claim.objects.create(
            claimant_name="Jane Doe",
            policy_number="POL-TEST-3",
            claim_type=Claim.ClaimType.MEDICAL,
            submitted_by=self.adjuster,
        )
        search_doc_id = f"test-claim-{claim.pk}-narrative-0"
        ClaimNarrative.objects.create(
            claim=claim, narrative_text="chunk one", chunk_index=0, search_doc_id=search_doc_id
        )
        with self.assertRaises(Exception):
            ClaimNarrative.objects.create(
                claim=claim, narrative_text="dup", chunk_index=1, search_doc_id=search_doc_id
            )

    def test_claim_summary_one_to_one(self):
        claim = Claim.objects.create(
            claimant_name="Jane Doe",
            policy_number="POL-TEST-4",
            claim_type=Claim.ClaimType.AUTO,
            submitted_by=self.adjuster,
        )
        summary = ClaimSummary.objects.create(
            claim=claim, ai_summary_text="stub summary", flagged_for_review=True, similar_claim_ids=[1, 2]
        )
        self.assertEqual(claim.summary, summary)
        self.assertTrue(claim.summary.flagged_for_review)

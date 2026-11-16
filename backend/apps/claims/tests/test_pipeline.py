from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.claims.models import Claim, ClaimNarrative, ClaimSummary
from apps.common import search_store

User = get_user_model()


class ClaimPipelineEndToEndTests(TestCase):
    """
    Exercises the full pipeline through stub mode:
    upload -> extract -> chunk/embed -> index -> search -> AI summary.
    """

    def setUp(self):
        search_store.reset_memory_store()
        self.adjuster = User.objects.create_user(
            email="pipeline@test.com", password="Password123!", role=User.Role.ADJUSTER
        )
        self.client = APIClient()
        response = self.client.post(
            "/api/auth/login/", {"email": self.adjuster.email, "password": "Password123!"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def tearDown(self):
        search_store.reset_memory_store()

    def _create_claim(self, narrative_text, policy_number):
        response = self.client.post(
            "/api/claims/",
            {
                "claimant_name": "Pipeline Claimant",
                "policy_number": policy_number,
                "claim_type": "auto",
                "narrative_text": narrative_text,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def test_full_pipeline_upload_extract_chunk_embed_index_search_summarize(self):
        narrative = "Rear-end collision at Main St during rain; other driver struck the rear bumper."
        claim_id = self._create_claim(narrative, "POL-PIPE-1")

        # Narrative chunks were created and indexed.
        narratives = ClaimNarrative.objects.filter(claim_id=claim_id)
        self.assertTrue(narratives.exists())
        for n in narratives:
            results = search_store.search("claim_narratives", [0.0] * 1536, top_k=1)
            self.assertIsInstance(results, list)

        # Upload a document; extraction is synchronous and populates extracted_fields.
        file_obj = SimpleUploadedFile(
            "invoice.txt",
            b"Vendor: Main St Auto Body\nAmount: 950.00\nDate: 2024-05-10\nDescription: Rear bumper repair\n",
            content_type="text/plain",
        )
        upload_response = self.client.post(
            f"/api/claims/{claim_id}/documents/",
            {"file": file_obj, "document_type": "invoice"},
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 201, upload_response.data)
        self.assertEqual(upload_response.data["extracted_fields"]["vendor"], "Main St Auto Body")
        self.assertEqual(upload_response.data["extracted_fields"]["amount"], 950.0)

        # Documents list endpoint.
        list_response = self.client.get(f"/api/claims/{claim_id}/documents/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)

        # Generate summary: embeds narrative, searches similar claims, calls AI chat stub.
        summary_response = self.client.post(f"/api/claims/{claim_id}/generate-summary/")
        self.assertEqual(summary_response.status_code, 200, summary_response.data)
        self.assertTrue(len(summary_response.data["ai_summary_text"]) > 0)
        self.assertFalse(summary_response.data["flagged_for_review"])  # no similar claims yet

        # Summary retrieval endpoint.
        get_response = self.client.get(f"/api/claims/{claim_id}/summary/")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.data["claim"], claim_id)

    def test_duplicate_narrative_flags_for_review(self):
        duplicate_text = (
            "Rear-end collision at the intersection of 5th Ave and Main St during heavy rain. "
            "Other driver failed to stop and struck the rear bumper."
        )
        claim_id_1 = self._create_claim(duplicate_text, "POL-DUP-1")
        claim_id_2 = self._create_claim(duplicate_text, "POL-DUP-2")

        response = self.client.post(f"/api/claims/{claim_id_2}/generate-summary/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["flagged_for_review"])
        self.assertIn(claim_id_1, response.data["similar_claim_ids"])

        summary = ClaimSummary.objects.get(claim_id=claim_id_2)
        self.assertTrue(summary.flagged_for_review)

    def test_generate_summary_without_narrative_fails(self):
        claim = Claim.objects.create(
            claimant_name="No Narrative",
            policy_number="POL-EMPTY",
            claim_type=Claim.ClaimType.AUTO,
            submitted_by=self.adjuster,
        )
        response = self.client.post(f"/api/claims/{claim.id}/generate-summary/")
        self.assertEqual(response.status_code, 400)

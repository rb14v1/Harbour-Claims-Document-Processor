from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.claims.models import Claim

User = get_user_model()


class ClaimApiPermissionTests(TestCase):
    def setUp(self):
        self.adjuster = User.objects.create_user(
            email="adjuster1@test.com", password="Password123!", role=User.Role.ADJUSTER
        )
        self.other_adjuster = User.objects.create_user(
            email="adjuster2@test.com", password="Password123!", role=User.Role.ADJUSTER
        )
        self.admin = User.objects.create_user(
            email="admin1@test.com", password="Password123!", role=User.Role.ADMIN, is_staff=True
        )

        self.own_claim = Claim.objects.create(
            claimant_name="Own Claimant",
            policy_number="POL-A",
            claim_type=Claim.ClaimType.AUTO,
            submitted_by=self.adjuster,
        )
        self.other_claim = Claim.objects.create(
            claimant_name="Other Claimant",
            policy_number="POL-B",
            claim_type=Claim.ClaimType.PROPERTY,
            submitted_by=self.other_adjuster,
        )

    def _auth(self, user):
        client = APIClient()
        response = client.post(
            "/api/auth/login/", {"email": user.email, "password": "Password123!"}, format="json"
        )
        token = response.data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def test_unauthenticated_request_rejected(self):
        client = APIClient()
        response = client.get("/api/claims/")
        self.assertEqual(response.status_code, 401)

    def test_adjuster_only_sees_own_claims(self):
        client = self._auth(self.adjuster)
        response = client.get("/api/claims/")
        self.assertEqual(response.status_code, 200)
        ids = [c["id"] for c in response.data["results"]]
        self.assertIn(self.own_claim.id, ids)
        self.assertNotIn(self.other_claim.id, ids)

    def test_adjuster_cannot_retrieve_other_adjusters_claim(self):
        client = self._auth(self.adjuster)
        response = client.get(f"/api/claims/{self.other_claim.id}/")
        self.assertEqual(response.status_code, 404)

    def test_admin_sees_all_claims(self):
        client = self._auth(self.admin)
        response = client.get("/api/claims/")
        ids = [c["id"] for c in response.data["results"]]
        self.assertIn(self.own_claim.id, ids)
        self.assertIn(self.other_claim.id, ids)

    def test_adjuster_can_create_claim(self):
        client = self._auth(self.adjuster)
        response = client.post(
            "/api/claims/",
            {
                "claimant_name": "New Claimant",
                "policy_number": "POL-NEW",
                "claim_type": "auto",
                "narrative_text": "A minor collision occurred in a parking lot.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["submitted_by"], self.adjuster.id)

    def test_adjuster_cannot_delete_claim(self):
        client = self._auth(self.adjuster)
        response = client.delete(f"/api/claims/{self.own_claim.id}/")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_delete_claim(self):
        client = self._auth(self.admin)
        response = client.delete(f"/api/claims/{self.own_claim.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Claim.objects.filter(id=self.own_claim.id).exists())

    def test_adjuster_cannot_override_denied_status(self):
        self.own_claim.status = Claim.Status.DENIED
        self.own_claim.save()
        client = self._auth(self.adjuster)
        response = client.patch(f"/api/claims/{self.own_claim.id}/", {"status": "approved"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.own_claim.refresh_from_db()
        self.assertEqual(self.own_claim.status, Claim.Status.DENIED)

    def test_admin_can_override_denied_status(self):
        self.own_claim.status = Claim.Status.DENIED
        self.own_claim.save()
        client = self._auth(self.admin)
        response = client.patch(f"/api/claims/{self.own_claim.id}/", {"status": "approved"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.own_claim.refresh_from_db()
        self.assertEqual(self.own_claim.status, Claim.Status.APPROVED)

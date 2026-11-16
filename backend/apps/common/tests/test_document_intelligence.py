from django.test import TestCase

from apps.common import document_intelligence


class DocumentIntelligenceStubTests(TestCase):
    def test_extracts_explicit_fields(self):
        text = b"Vendor: Acme Auto Repair\nAmount: $456.78\nDate: 2024-03-02\nDescription: Bumper replacement\n"
        fields = document_intelligence.extract_fields(text, "invoice")

        self.assertEqual(fields["vendor"], "Acme Auto Repair")
        self.assertEqual(fields["amount"], 456.78)
        self.assertEqual(fields["date"], "2024-03-02")
        self.assertEqual(fields["description"], "Bumper replacement")

    def test_deterministic_for_same_bytes(self):
        text = b"no structured fields here, just free text describing a claim"
        first = document_intelligence.extract_fields(text, "photo")
        second = document_intelligence.extract_fields(text, "photo")
        self.assertEqual(first, second)

    def test_different_bytes_produce_different_fallback_values(self):
        fields_a = document_intelligence.extract_fields(b"document A content", "photo")
        fields_b = document_intelligence.extract_fields(b"document B content", "photo")
        self.assertNotEqual(fields_a["vendor"], fields_b["vendor"])

    def test_all_expected_keys_present(self):
        fields = document_intelligence.extract_fields(b"some text", "medical_bill")
        self.assertEqual(set(fields.keys()), {"vendor", "amount", "date", "description"})

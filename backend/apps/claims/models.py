from django.conf import settings
from django.db import models


class Claim(models.Model):
    class ClaimType(models.TextChoices):
        AUTO = "auto", "Auto"
        PROPERTY = "property", "Property"
        MEDICAL = "medical", "Medical"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"

    claimant_name = models.CharField(max_length=255)
    policy_number = models.CharField(max_length=64)
    claim_type = models.CharField(max_length=20, choices=ClaimType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submitted_claims"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Claim #{self.pk} - {self.claimant_name} ({self.policy_number})"


class ClaimDocument(models.Model):
    class DocumentType(models.TextChoices):
        INVOICE = "invoice", "Invoice"
        POLICE_REPORT = "police_report", "Police Report"
        MEDICAL_BILL = "medical_bill", "Medical Bill"
        PHOTO = "photo", "Photo"

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    blob_path = models.CharField(max_length=512)
    extracted_fields = models.JSONField(default=dict, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_document_type_display()} for claim #{self.claim_id}"


class ClaimNarrative(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="narratives")
    narrative_text = models.TextField()
    chunk_index = models.PositiveIntegerField(default=0)
    search_doc_id = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["claim_id", "chunk_index"]

    def __str__(self):
        return f"Narrative chunk {self.chunk_index} for claim #{self.claim_id}"


class ClaimSummary(models.Model):
    claim = models.OneToOneField(Claim, on_delete=models.CASCADE, related_name="summary")
    ai_summary_text = models.TextField()
    flagged_for_review = models.BooleanField(default=False)
    similar_claim_ids = models.JSONField(default=list, blank=True)
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Summary for claim #{self.claim_id}"

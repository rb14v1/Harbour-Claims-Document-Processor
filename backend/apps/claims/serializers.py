from rest_framework import serializers

from .models import Claim, ClaimDocument, ClaimNarrative, ClaimSummary


class ClaimDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimDocument
        fields = ["id", "claim", "document_type", "blob_path", "extracted_fields", "uploaded_at"]
        read_only_fields = ["id", "claim", "blob_path", "extracted_fields", "uploaded_at"]


class ClaimNarrativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimNarrative
        fields = ["id", "claim", "narrative_text", "chunk_index", "search_doc_id", "created_at"]
        read_only_fields = fields


class ClaimSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimSummary
        fields = ["id", "claim", "ai_summary_text", "flagged_for_review", "similar_claim_ids", "generated_at"]
        read_only_fields = fields


class ClaimSerializer(serializers.ModelSerializer):
    submitted_by_email = serializers.EmailField(source="submitted_by.email", read_only=True)
    narrative_text = serializers.CharField(write_only=True, required=False, allow_blank=True)
    documents = ClaimDocumentSerializer(many=True, read_only=True)
    summary = ClaimSummarySerializer(read_only=True)

    class Meta:
        model = Claim
        fields = [
            "id",
            "claimant_name",
            "policy_number",
            "claim_type",
            "status",
            "submitted_by",
            "submitted_by_email",
            "created_at",
            "updated_at",
            "narrative_text",
            "documents",
            "summary",
        ]
        read_only_fields = ["id", "submitted_by", "created_at", "updated_at"]

    def validate_status(self, value):
        instance = getattr(self, "instance", None)
        if instance and instance.status == Claim.Status.DENIED and value != Claim.Status.DENIED:
            request = self.context.get("request")
            user = getattr(request, "user", None)
            if not user or user.role != "admin":
                raise serializers.ValidationError(
                    "Only an admin can override a denied claim's status."
                )
        return value

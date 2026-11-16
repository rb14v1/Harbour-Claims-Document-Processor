from django.contrib import admin

from .models import Claim, ClaimDocument, ClaimNarrative, ClaimSummary


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ["id", "claimant_name", "policy_number", "claim_type", "status", "submitted_by", "created_at"]
    list_filter = ["claim_type", "status"]
    search_fields = ["claimant_name", "policy_number"]


@admin.register(ClaimDocument)
class ClaimDocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "claim", "document_type", "uploaded_at"]
    list_filter = ["document_type"]


@admin.register(ClaimNarrative)
class ClaimNarrativeAdmin(admin.ModelAdmin):
    list_display = ["id", "claim", "chunk_index", "search_doc_id"]


@admin.register(ClaimSummary)
class ClaimSummaryAdmin(admin.ModelAdmin):
    list_display = ["id", "claim", "flagged_for_review", "generated_at"]
    list_filter = ["flagged_for_review"]

from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.common import blob_store, document_intelligence

from . import services
from .models import Claim, ClaimDocument, ClaimSummary
from .permissions import IsAdjusterOrAdmin, IsAdminRole
from .serializers import (
    ClaimDocumentSerializer,
    ClaimSerializer,
    ClaimSummarySerializer,
)


class ClaimViewSet(viewsets.ModelViewSet):
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdjusterOrAdmin]

    def get_queryset(self):
        """
        Queryset-level scoping: admins see every claim; adjusters only see
        claims they personally submitted (their own working queue).
        """
        user = self.request.user
        base = Claim.objects.select_related("submitted_by").prefetch_related("documents", "narratives")
        if user.role == "admin":
            return base
        return base.filter(submitted_by=user)

    def get_permissions(self):
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsAdminRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        narrative_text = serializer.validated_data.pop("narrative_text", "")
        claim = serializer.save(submitted_by=self.request.user)
        if narrative_text:
            services.index_narrative_chunks(claim.narratives.model, claim, narrative_text)

    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = serializer.validated_data.get("status", instance.status)
        if (
            instance.status == Claim.Status.DENIED
            and new_status != Claim.Status.DENIED
            and self.request.user.role != "admin"
        ):
            raise PermissionDenied("Only an admin can override a denied claim's status.")
        narrative_text = serializer.validated_data.pop("narrative_text", None)
        claim = serializer.save()
        if narrative_text:
            services.index_narrative_chunks(claim.narratives.model, claim, narrative_text)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="documents",
        parser_classes=[MultiPartParser, FormParser],
    )
    def documents(self, request, pk=None):
        claim = self.get_object()

        if request.method == "GET":
            docs = claim.documents.all()
            return Response(ClaimDocumentSerializer(docs, many=True).data)

        file_obj = request.FILES.get("file")
        document_type = request.data.get("document_type")
        if not file_obj or not document_type:
            raise ValidationError("'file' and 'document_type' are required.")
        if document_type not in ClaimDocument.DocumentType.values:
            raise ValidationError(f"Invalid document_type. Must be one of {ClaimDocument.DocumentType.values}.")

        file_obj.seek(0)
        document_bytes = file_obj.read()
        file_obj.seek(0)

        blob_path = blob_store.upload_document(
            file_obj, container="claim-documents", blob_name=f"claim-{claim.pk}-{file_obj.name}"
        )
        extracted_fields = document_intelligence.extract_fields(document_bytes, document_type)

        doc = ClaimDocument.objects.create(
            claim=claim,
            document_type=document_type,
            blob_path=blob_path,
            extracted_fields=extracted_fields,
        )

        # If the claim has no narrative yet, bootstrap one from the
        # extracted description so the similarity pipeline has text to work
        # with even when the caller didn't submit narrative_text directly.
        if not claim.narratives.exists() and extracted_fields.get("description"):
            services.index_narrative_chunks(
                claim.narratives.model, claim, extracted_fields["description"]
            )

        return Response(ClaimDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="generate-summary")
    def generate_summary(self, request, pk=None):
        claim = self.get_object()
        data = services.generate_claim_summary_data(claim, claim.narratives.all(), claim.documents.all())
        if data is None:
            raise ValidationError(
                "This claim has no narrative text yet. Submit narrative_text or upload a document first."
            )
        summary, _ = ClaimSummary.objects.update_or_create(claim=claim, defaults=data)
        return Response(ClaimSummarySerializer(summary).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        claim = self.get_object()
        try:
            return Response(ClaimSummarySerializer(claim.summary).data)
        except ClaimSummary.DoesNotExist:
            return Response({"detail": "No summary generated yet."}, status=status.HTTP_404_NOT_FOUND)

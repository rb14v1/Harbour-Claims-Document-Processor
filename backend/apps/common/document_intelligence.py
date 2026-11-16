"""
Thin wrapper around azure-ai-documentintelligence.

Real client call is used when AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and
AZURE_DOCUMENT_INTELLIGENCE_KEY are both set. In production this would call
the `prebuilt-invoice` model for document_type="invoice"/"medical_bill" and
`prebuilt-receipt` for everything else (see `_model_for_document_type`).

Otherwise falls back to a deterministic stub: it reads the raw text of the
uploaded document (uploads in tests/dev are plain text or simple text-like
files) and produces fake-but-structured extracted fields via a mix of simple
regex parsing and a SHA256-seeded value derivation, so results are
reproducible across runs for the same input bytes.
"""

import hashlib
import re

from decouple import config

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = config("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", default="")
AZURE_DOCUMENT_INTELLIGENCE_KEY = config("AZURE_DOCUMENT_INTELLIGENCE_KEY", default="")


def _is_real():
    return bool(AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY)


def _model_for_document_type(document_type):
    # Production model selection: invoices/medical bills use prebuilt-invoice,
    # everything else (police reports, photos) uses prebuilt-receipt as a
    # reasonable general-purpose structured extractor.
    if document_type in ("invoice", "medical_bill"):
        return "prebuilt-invoice"
    return "prebuilt-receipt"


def extract_fields(document_bytes, document_type):
    """
    Returns a dict: {"vendor": str, "amount": float, "date": "YYYY-MM-DD",
    "description": str} extracted from `document_bytes`.
    """
    if _is_real():
        return _extract_real(document_bytes, document_type)
    return _extract_stub(document_bytes, document_type)


def _extract_real(document_bytes, document_type):  # pragma: no cover - requires real Azure creds
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    client = DocumentIntelligenceClient(
        endpoint=AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
        credential=AzureKeyCredential(AZURE_DOCUMENT_INTELLIGENCE_KEY),
    )
    model_id = _model_for_document_type(document_type)
    poller = client.begin_analyze_document(model_id, document_bytes)
    result = poller.result()

    fields = {}
    if result.documents:
        doc = result.documents[0]
        fields = doc.fields or {}

    def _field_value(name, default=None):
        f = fields.get(name)
        if not f:
            return default
        return getattr(f, "value_string", None) or getattr(f, "content", default)

    vendor = _field_value("VendorName") or _field_value("MerchantName") or "Unknown Vendor"
    amount_field = fields.get("InvoiceTotal") or fields.get("Total")
    amount = 0.0
    if amount_field is not None:
        amount_value = getattr(amount_field, "value_currency", None)
        amount = float(getattr(amount_value, "amount", 0.0)) if amount_value else 0.0
    date = _field_value("InvoiceDate") or _field_value("TransactionDate") or ""
    description = result.content[:500] if getattr(result, "content", None) else ""

    return {
        "vendor": vendor,
        "amount": round(amount, 2),
        "date": str(date),
        "description": description,
    }


def _extract_stub(document_bytes, document_type):
    if isinstance(document_bytes, str):
        document_bytes = document_bytes.encode("utf-8")
    text = document_bytes.decode("utf-8", errors="ignore")
    seed = hashlib.sha256(document_bytes).hexdigest()

    vendor = _match(text, r"Vendor:\s*(.+)") or f"Vendor-{seed[:6].upper()}"

    amount_match = _match(text, r"Amount:\s*\$?\s*([0-9]+(?:\.[0-9]+)?)")
    if amount_match:
        amount = round(float(amount_match), 2)
    else:
        amount = round((int(seed[:6], 16) % 500000) / 100, 2)

    date_match = _match(text, r"Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")
    if date_match:
        date = date_match
    else:
        year = 2022 + (int(seed[6], 16) % 4)
        month = (int(seed[7:9], 16) % 12) + 1
        day = (int(seed[9:11], 16) % 28) + 1
        date = f"{year:04d}-{month:02d}-{day:02d}"

    description_match = _match(text, r"Description:\s*(.+)")
    if description_match:
        description = description_match
    elif text.strip():
        description = text.strip().splitlines()[0][:200]
    else:
        description = f"Auto-generated {document_type} description {seed[:10]}"

    return {
        "vendor": vendor,
        "amount": amount,
        "date": date,
        "description": description,
    }


def _match(text, pattern):
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None

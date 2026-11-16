"""
Shared pipeline logic for turning claim narrative text into indexed,
searchable chunks, and for generating AI claim summaries. Used by both the
API views (apps/claims/views.py) and the seed data migration, so the
upload -> extract -> chunk/embed -> index -> search -> summarize pipeline is
defined in exactly one place.
"""

from django.conf import settings

from apps.common import ai, search_store

SEARCH_INDEX_NAME = "claim_narratives"


def chunk_text(text, chunk_size=None):
    """Splits `text` into a list of non-empty, whitespace-trimmed chunks."""
    chunk_size = chunk_size or getattr(settings, "NARRATIVE_CHUNK_SIZE", 400)
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    for start in range(0, len(text), chunk_size):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def index_narrative_chunks(narrative_model, claim, narrative_text):
    """
    Chunks `narrative_text`, creates one `narrative_model` row per chunk, and
    embeds + upserts each chunk into the search_store index. Returns the list
    of created narrative rows. `narrative_model` may be the live ClaimNarrative
    model or a historical (migration) version of it -- both support the same
    field access used here.
    """
    chunks = chunk_text(narrative_text)
    created = []
    items = []
    existing_count = narrative_model.objects.filter(claim=claim).count()
    for offset, chunk in enumerate(chunks):
        chunk_index = existing_count + offset
        search_doc_id = f"claim-{claim.pk}-narrative-{chunk_index}"
        narrative = narrative_model.objects.create(
            claim=claim,
            narrative_text=chunk,
            chunk_index=chunk_index,
            search_doc_id=search_doc_id,
        )
        created.append(narrative)
        vector = ai.generate_embedding(chunk)
        items.append(
            {
                "id": search_doc_id,
                "vector": vector,
                "payload": {"claim_id": claim.pk, "narrative_id": narrative.pk, "text": chunk},
            }
        )
    if items:
        search_store.upsert_chunks(SEARCH_INDEX_NAME, items)
    return created


def build_summary_prompt(claim, documents, combined_narrative, similar_claim_ids):
    extracted_lines = []
    for doc in documents:
        fields = doc.extracted_fields or {}
        extracted_lines.append(
            f"- {doc.get_document_type_display() if hasattr(doc, 'get_document_type_display') else doc.document_type}: "
            f"vendor={fields.get('vendor')}, amount={fields.get('amount')}, date={fields.get('date')}"
        )
    extracted_block = "\n".join(extracted_lines) or "No documents uploaded yet."
    similar_block = (
        f"{len(similar_claim_ids)} similar historical claim(s) found: {similar_claim_ids}"
        if similar_claim_ids
        else "No similar historical claims found."
    )
    return (
        f"Summarize insurance claim #{claim.pk} for {claim.claimant_name} "
        f"(policy {claim.policy_number}, type {claim.claim_type}, status {claim.status}).\n"
        f"Extracted document fields:\n{extracted_block}\n"
        f"Claim narrative: {combined_narrative}\n"
        f"Similarity check: {similar_block}"
    )


def generate_claim_summary_data(claim, narrative_qs, document_qs):
    """
    Runs the similarity search + AI summary step for `claim`. Returns a dict
    suitable for creating/updating a ClaimSummary: {ai_summary_text,
    flagged_for_review, similar_claim_ids}. Returns None if there is no
    narrative text to summarize yet.
    """
    narratives = list(narrative_qs)
    if not narratives:
        return None

    combined_narrative = " ".join(n.narrative_text for n in narratives)
    own_ids = {n.search_doc_id for n in narratives}

    query_vector = ai.generate_embedding(combined_narrative)
    results = search_store.search(SEARCH_INDEX_NAME, query_vector, top_k=10, exclude_ids=own_ids)

    similar_claim_ids = []
    max_score = 0.0
    for result in results:
        candidate_claim_id = result["payload"].get("claim_id")
        if candidate_claim_id is None or candidate_claim_id == claim.pk:
            continue
        max_score = max(max_score, result["score"])
        if candidate_claim_id not in similar_claim_ids:
            similar_claim_ids.append(candidate_claim_id)

    threshold = getattr(settings, "SIMILARITY_FLAG_THRESHOLD", 0.92)
    flagged = max_score >= threshold

    documents = list(document_qs)
    prompt = build_summary_prompt(claim, documents, combined_narrative, similar_claim_ids)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a claims-processing assistant. Summarize the claim concisely "
                "and flag any potential duplicate or fraud pattern."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    ai_summary_text = ai.chat_completion(messages)
    if flagged:
        ai_summary_text += " [FLAGGED FOR REVIEW: similarity to prior claim(s) exceeds threshold]"

    return {
        "ai_summary_text": ai_summary_text,
        "flagged_for_review": flagged,
        "similar_claim_ids": similar_claim_ids,
    }

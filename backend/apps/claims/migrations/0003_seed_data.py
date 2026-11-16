"""
Idempotent seed data migration. Creates demo users, claims, documents,
narrative chunks (chunked + embedded + indexed into the search_store
in-memory/real index), and a handful of generated AI summaries -- including
at least one flagged_for_review=True to demonstrate the similarity-flagging
logic (two claims deliberately share a near-identical narrative).

This runs the real apps/common/* module code (document_intelligence, ai,
search_store), which is deterministic/stub-safe with no external network
calls when the matching AZURE_* env vars are blank (the default for local
dev/test). Password hashing uses django.contrib.auth.hashers.make_password
directly -- never set_password() on a historical model.
"""

import io

from django.contrib.auth.hashers import make_password
from django.db import migrations


def seed_data(apps, schema_editor):
    User = apps.get_model("users", "User")
    Claim = apps.get_model("claims", "Claim")
    ClaimDocument = apps.get_model("claims", "ClaimDocument")
    ClaimNarrative = apps.get_model("claims", "ClaimNarrative")
    ClaimSummary = apps.get_model("claims", "ClaimSummary")

    from apps.common import ai, blob_store, document_intelligence, search_store

    adjuster, _ = User.objects.get_or_create(
        email="adjuster@claims.demo",
        defaults={
            "first_name": "Alice",
            "last_name": "Adjuster",
            "role": "adjuster",
            "is_staff": False,
            "is_superuser": False,
            "is_active": True,
            "password": make_password("Password123!"),
        },
    )
    admin, _ = User.objects.get_or_create(
        email="admin@claims.demo",
        defaults={
            "first_name": "Amir",
            "last_name": "Admin",
            "role": "admin",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "password": make_password("Password123!"),
        },
    )

    # Two claims deliberately share this narrative verbatim so their stub
    # embeddings are identical (cosine similarity 1.0), guaranteeing the
    # similarity-flagging demo works deterministically.
    duplicate_narrative = (
        "Rear-end collision at the intersection of 5th Ave and Main St during heavy rain. "
        "Other driver failed to stop in time and struck the rear bumper, causing moderate damage "
        "to the trunk and rear bumper panel."
    )

    claims_spec = [
        dict(
            claimant_name="John Carter", policy_number="POL-1001", claim_type="auto",
            status="submitted", submitted_by=adjuster, doc_type="invoice",
            narrative=duplicate_narrative,
            invoice_text="Vendor: Main St Auto Body\nAmount: 1450.00\nDate: 2024-02-10\n"
                          "Description: Rear bumper and trunk panel repair\n",
            generate_summary=True,
        ),
        dict(
            claimant_name="Maria Lopez", policy_number="POL-1002", claim_type="auto",
            status="under_review", submitted_by=adjuster, doc_type="police_report",
            narrative=duplicate_narrative,
            invoice_text="Vendor: 5th Ave Collision Center\nAmount: 1510.50\nDate: 2024-02-11\n"
                         "Description: Rear end collision damage report\n",
            generate_summary=True,
        ),
        dict(
            claimant_name="David Kim", policy_number="POL-1003", claim_type="property",
            status="approved", submitted_by=admin, doc_type="invoice",
            narrative=(
                "Kitchen fire caused smoke damage to cabinets and ceiling; fire department "
                "responded within 10 minutes and contained the fire to the kitchen area."
            ),
            invoice_text="Vendor: CleanSweep Restoration\nAmount: 3200.00\nDate: 2024-01-20\n"
                         "Description: Smoke damage cleanup and cabinet replacement\n",
            generate_summary=True,
        ),
        dict(
            claimant_name="Sarah Connor", policy_number="POL-1004", claim_type="medical",
            status="submitted", submitted_by=adjuster, doc_type="medical_bill",
            narrative=(
                "Patient treated for a fractured wrist after a slip-and-fall accident at a "
                "grocery store entrance during icy conditions."
            ),
            invoice_text="Vendor: Riverside Medical Center\nAmount: 2875.40\nDate: 2024-03-05\n"
                         "Description: Wrist fracture treatment and cast\n",
            generate_summary=False,
        ),
        dict(
            claimant_name="Tom Nguyen", policy_number="POL-1005", claim_type="property",
            status="denied", submitted_by=admin, doc_type="photo",
            narrative=(
                "Storm damage to roof shingles reported after a hailstorm; adjuster inspection "
                "found pre-existing wear inconsistent with storm damage claim."
            ),
            invoice_text="Vendor: Summit Roofing Estimates\nAmount: 4100.00\nDate: 2024-01-05\n"
                         "Description: Roof shingle storm damage estimate\n",
            generate_summary=True,
        ),
        dict(
            claimant_name="Priya Patel", policy_number="POL-1006", claim_type="auto",
            status="approved", submitted_by=adjuster, doc_type="invoice",
            narrative=(
                "Minor fender bender in a parking lot resulting in a cracked tail light and "
                "scratched rear quarter panel paint."
            ),
            invoice_text="Vendor: QuickFix Auto\nAmount: 410.00\nDate: 2024-02-28\n"
                         "Description: Tail light replacement and paint touch-up\n",
            generate_summary=False,
        ),
        dict(
            claimant_name="Liam O'Connor", policy_number="POL-1007", claim_type="medical",
            status="under_review", submitted_by=admin, doc_type="medical_bill",
            narrative=(
                "Patient sustained a lower back strain while lifting a package at work; "
                "physical therapy recommended for six weeks."
            ),
            invoice_text="Vendor: Westside Physical Therapy\nAmount: 1225.00\nDate: 2024-03-18\n"
                         "Description: Lower back strain physical therapy sessions\n",
            generate_summary=False,
        ),
        dict(
            claimant_name="Emma Davis", policy_number="POL-1008", claim_type="property",
            status="submitted", submitted_by=adjuster, doc_type="photo",
            narrative=(
                "Basement flooding after heavy rainfall overwhelmed the sump pump, damaging "
                "stored furniture and flooring materials."
            ),
            invoice_text="Vendor: AquaDry Restoration\nAmount: 2750.00\nDate: 2024-03-22\n"
                         "Description: Basement flood water extraction and flooring repair\n",
            generate_summary=False,
        ),
    ]

    created_claims = []
    for spec in claims_spec:
        claim, created = Claim.objects.get_or_create(
            policy_number=spec["policy_number"],
            defaults={
                "claimant_name": spec["claimant_name"],
                "claim_type": spec["claim_type"],
                "status": spec["status"],
                "submitted_by": spec["submitted_by"],
            },
        )
        created_claims.append((claim, spec))

        if not created:
            continue  # already seeded previously; keep migration idempotent

        # --- document upload + extraction (stub or real) ---
        document_bytes = spec["invoice_text"].encode("utf-8")
        file_obj = io.BytesIO(document_bytes)
        file_obj.name = f"{spec['policy_number']}-{spec['doc_type']}.txt"
        blob_path = blob_store.upload_document(
            file_obj, container="claim-documents", blob_name=f"claim-{claim.pk}-{spec['doc_type']}.txt"
        )
        extracted_fields = document_intelligence.extract_fields(document_bytes, spec["doc_type"])
        ClaimDocument.objects.create(
            claim=claim,
            document_type=spec["doc_type"],
            blob_path=blob_path,
            extracted_fields=extracted_fields,
        )

        # --- narrative chunking + embedding + indexing ---
        narrative_text = spec["narrative"]
        chunk_size = 400
        chunks = [
            narrative_text[i : i + chunk_size].strip()
            for i in range(0, len(narrative_text), chunk_size)
            if narrative_text[i : i + chunk_size].strip()
        ] or [narrative_text]

        index_items = []
        for chunk_index, chunk in enumerate(chunks):
            search_doc_id = f"claim-{claim.pk}-narrative-{chunk_index}"
            ClaimNarrative.objects.create(
                claim=claim,
                narrative_text=chunk,
                chunk_index=chunk_index,
                search_doc_id=search_doc_id,
            )
            vector = ai.generate_embedding(chunk)
            index_items.append(
                {
                    "id": search_doc_id,
                    "vector": vector,
                    "payload": {"claim_id": claim.pk, "narrative_id": None, "text": chunk},
                }
            )
        search_store.upsert_chunks("claim_narratives", index_items)

    # --- generate AI summaries (similarity search + chat stub) for selected claims ---
    similarity_threshold = 0.92
    for claim, spec in created_claims:
        if not spec.get("generate_summary"):
            continue
        if ClaimSummary.objects.filter(claim=claim).exists():
            continue

        narratives = list(ClaimNarrative.objects.filter(claim=claim))
        if not narratives:
            continue
        combined_text = " ".join(n.narrative_text for n in narratives)
        own_ids = {n.search_doc_id for n in narratives}

        query_vector = ai.generate_embedding(combined_text)
        results = search_store.search("claim_narratives", query_vector, top_k=10, exclude_ids=own_ids)

        similar_claim_ids = []
        max_score = 0.0
        for result in results:
            candidate_claim_id = result["payload"].get("claim_id")
            if candidate_claim_id is None or candidate_claim_id == claim.pk:
                continue
            max_score = max(max_score, result["score"])
            if candidate_claim_id not in similar_claim_ids:
                similar_claim_ids.append(candidate_claim_id)

        flagged = max_score >= similarity_threshold

        documents = list(ClaimDocument.objects.filter(claim=claim))
        extracted_lines = [
            f"- {doc.document_type}: vendor={doc.extracted_fields.get('vendor')}, "
            f"amount={doc.extracted_fields.get('amount')}, date={doc.extracted_fields.get('date')}"
            for doc in documents
        ]
        prompt = (
            f"Summarize insurance claim #{claim.pk} for {claim.claimant_name} "
            f"(policy {claim.policy_number}, type {claim.claim_type}, status {claim.status}).\n"
            f"Extracted document fields:\n" + "\n".join(extracted_lines) + "\n"
            f"Claim narrative: {combined_text}\n"
            f"Similarity check: {len(similar_claim_ids)} similar claim(s) found: {similar_claim_ids}"
        )
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

        ClaimSummary.objects.create(
            claim=claim,
            ai_summary_text=ai_summary_text,
            flagged_for_review=flagged,
            similar_claim_ids=similar_claim_ids,
        )


def unseed_data(apps, schema_editor):
    User = apps.get_model("users", "User")
    Claim = apps.get_model("claims", "Claim")

    policy_numbers = [f"POL-100{i}" for i in range(1, 9)]
    Claim.objects.filter(policy_number__in=policy_numbers).delete()
    User.objects.filter(email__in=["adjuster@claims.demo", "admin@claims.demo"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("claims", "0002_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_data, unseed_data),
    ]

import sys

from django.apps import AppConfig


class ClaimsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.claims"
    label = "claims"

    def ready(self):
        # Only warm up the in-memory search index when actually serving the
        # app (runserver). Every other management command (test, migrate,
        # makemigrations, check, shell, etc.) skips this: the schema may not
        # exist yet, and determinism/speed matter more there than a warm
        # search index.
        if "runserver" not in sys.argv:
            return
        try:
            self._reindex_narratives()
        except Exception:
            # Best-effort warm-up only; the search index is also rebuilt
            # lazily whenever narratives are created/updated via the API.
            pass

    def _reindex_narratives(self):
        """
        Rebuilds the in-memory search_store index from existing ClaimNarrative
        rows on process startup. This is only meaningful when running against
        the in-memory search_store fallback (no real Azure AI Search
        configured), since that fallback does not persist across process
        restarts (e.g. `runserver` reloads).
        """
        from apps.common import ai, search_store

        if search_store._is_real():
            return

        from .models import ClaimNarrative

        items = []
        for narrative in ClaimNarrative.objects.all():
            vector = ai.generate_embedding(narrative.narrative_text)
            items.append(
                {
                    "id": narrative.search_doc_id,
                    "vector": vector,
                    "payload": {
                        "claim_id": narrative.claim_id,
                        "narrative_id": narrative.id,
                        "text": narrative.narrative_text,
                    },
                }
            )
        if items:
            search_store.upsert_chunks("claim_narratives", items)

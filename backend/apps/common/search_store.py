"""
Thin wrapper around azure-search-documents (vector + hybrid search).

Real `SearchClient` is used against an index when AZURE_SEARCH_ENDPOINT and
AZURE_SEARCH_KEY are both set. Otherwise falls back to an in-process,
in-memory list of {id, vector, payload} per index name, with cosine-similarity
top-k search implemented in plain Python (no external deps).

The in-memory fallback only needs to work within a single test/process run
(like Qdrant's :memory: mode) -- it is not persisted to disk. apps/claims
re-populates it from ClaimNarrative rows on application startup outside of
tests/migrations (see apps/claims/apps.py) so the demo stays usable across
`runserver` restarts even without real Azure Search configured.
"""

import math

from decouple import config

AZURE_SEARCH_ENDPOINT = config("AZURE_SEARCH_ENDPOINT", default="")
AZURE_SEARCH_KEY = config("AZURE_SEARCH_KEY", default="")

# index_name -> list[{"id": str, "vector": list[float], "payload": dict}]
_MEMORY_STORE = {}


def _is_real():
    return bool(AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY)


def _real_client(index_name):  # pragma: no cover - requires real Azure creds
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=index_name,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY),
    )


def reset_memory_store():
    """Test helper: clears all in-memory indexes."""
    _MEMORY_STORE.clear()


def upsert_chunks(index_name, items):
    """
    `items` is a list of {"id": str, "vector": list[float], "payload": dict}.
    Upserts (replacing by id) into the named index.
    """
    if _is_real():  # pragma: no cover - requires real Azure creds
        client = _real_client(index_name)
        documents = [
            {"id": item["id"], "vector": item["vector"], **item["payload"]}
            for item in items
        ]
        client.upload_documents(documents=documents)
        return

    store = _MEMORY_STORE.setdefault(index_name, [])
    incoming_ids = {item["id"] for item in items}
    store[:] = [entry for entry in store if entry["id"] not in incoming_ids] + list(items)


def search(index_name, query_vector, top_k=5, exclude_ids=None):
    """
    Returns up to `top_k` entries as {"id": str, "score": float, "payload": dict}
    sorted by descending cosine similarity to `query_vector`, excluding any id
    present in `exclude_ids`.
    """
    exclude_ids = set(exclude_ids or [])

    if _is_real():  # pragma: no cover - requires real Azure creds
        client = _real_client(index_name)
        from azure.search.documents.models import VectorizedQuery

        vector_query = VectorizedQuery(vector=query_vector, k_nearest_neighbors=top_k, fields="vector")
        results = client.search(search_text=None, vector_queries=[vector_query], top=top_k)
        output = []
        for r in results:
            if r["id"] in exclude_ids:
                continue
            payload = {k: v for k, v in r.items() if k not in ("id", "@search.score")}
            output.append({"id": r["id"], "score": r.get("@search.score", 0.0), "payload": payload})
        return output[:top_k]

    store = _MEMORY_STORE.get(index_name, [])
    scored = []
    for entry in store:
        if entry["id"] in exclude_ids:
            continue
        score = _cosine_similarity(query_vector, entry["vector"])
        scored.append({"id": entry["id"], "score": score, "payload": entry["payload"]})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

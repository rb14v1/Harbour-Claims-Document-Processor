# Claims Document Processor

A full-stack demo insurance claims processing app: adjusters upload claim
documents, the system extracts structured fields, chunks and embeds the
claim narrative, indexes it for similar/duplicate-claim lookup, and generates
an AI summary that flags potential duplicate or fraud patterns.

Stack: React (Vite + TypeScript) frontend, Django 5 + Django REST Framework
backend, PostgreSQL (or SQLite in dev/test), JWT auth, and five Azure service
integrations that each run in a deterministic local stub mode by default.

## Quick start (dev / stub mode, SQLite)

```powershell
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py runserver
```

`backend/.env` is already set up for this (`USE_SQLITE=True`, all `AZURE_*`
vars blank). `manage.py migrate` applies schema + the idempotent seed data
migration, so the demo logins and sample claims below are available
immediately.

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 - the Vite dev server proxies `/api` to
`http://localhost:8000` (see `frontend/vite.config.ts`).

## Demo logins

| Role     | Email                 | Password      |
|----------|------------------------|---------------|
| Adjuster | adjuster@claims.demo  | Password123!  |
| Admin    | admin@claims.demo     | Password123!  |

Seed data (created by `apps/claims/migrations/0003_seed_data.py`): 8 claims
spanning auto/property/medical types and all four statuses, each with one
uploaded document (extracted fields populated) and indexed narrative chunks.
Four of the claims have a generated `ClaimSummary`; two of those (POL-1001 and
POL-1002) deliberately share an identical narrative so the similarity search
flags them both `flagged_for_review=True`, demonstrating the
duplicate/fraud-pattern detection logic end to end.

## Running the real stack (Postgres, still-stubbed Azure)

Set `USE_SQLITE=False` in `backend/.env` (Postgres connection details are
already filled in for a local server at `localhost:5432`, db/user/pass
`claims_document_processor`/`claims_document_processor`/`claims_document_processor`).
Leave every `AZURE_*` var blank and all five integrations keep running in
stub mode -- no network calls, no cost, no real Azure resources required.
Then run `manage.py migrate` as usual.

## Running tests

```powershell
cd backend
venv\Scripts\python manage.py test
```

Tests always run with `USE_SQLITE=True` and every Azure integration stubbed,
so the suite needs zero external dependencies or credentials and is safe for
CI.

## Architecture: what's real vs. stubbed

Every external integration lives in `backend/apps/common/` as a small
dual-path module with one function signature regardless of mode -- callers
never know which mode is active.

- **Blob storage** (`blob_store.py`, wraps `azure-storage-blob`): uploaded
  claim documents go to a real Azure `BlobServiceClient` when
  `AZURE_STORAGE_CONNECTION_STRING` is set; otherwise they're written to/read
  from local disk under `MEDIA_ROOT/blob_stub/<container>/`.
- **Document Intelligence** (`document_intelligence.py`, wraps
  `azure-ai-documentintelligence`): calls the real
  `prebuilt-invoice`/`prebuilt-receipt` models when
  `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` + `_KEY` are set; otherwise a
  deterministic stub parses the uploaded text (or derives values via a
  SHA256 seed) into `{vendor, amount, date, description}`.
- **AI (chat + embeddings)** (`ai.py`, wraps Azure OpenAI via the `openai`
  SDK's `AzureOpenAI` client): real chat completions
  (`OPENAI_CHAT_MODEL`, default `gpt-5.6-sol`) and embeddings
  (`OPENAI_EMBEDDING_MODEL`, default `text-embedding-3-large`, 1536 dims)
  when `AZURE_OPENAI_ENDPOINT` + `_API_KEY` are set; otherwise deterministic
  SHA256-seeded stub text and vectors.
- **Search** (`search_store.py`, wraps `azure-search-documents`): real
  `SearchClient` vector search against the `claim_narratives` index when
  `AZURE_SEARCH_ENDPOINT` + `_KEY` are set; otherwise an in-process,
  in-memory `{id, vector, payload}` list per index with plain-Python
  cosine-similarity top-k search. This fallback only persists for the life
  of one process (like Qdrant's `:memory:` mode); `apps/claims/apps.py`
  re-warms it from `ClaimNarrative` rows whenever `runserver` starts, so the
  demo keeps working across restarts without real Azure Search.
- **Database**: plain relational PostgreSQL (or SQLite in dev/test) -- no
  pgvector extension, no vector columns. All vector/embedding storage goes
  through the `search_store` abstraction above instead.

## Pipeline

1. **Upload**: `POST /api/claims/{id}/documents/` with a file + `document_type`
   stores it via `blob_store.upload_document` and synchronously extracts
   fields via `document_intelligence.extract_fields` into a `ClaimDocument`.
2. **Chunk + embed + index**: narrative text (submitted directly on claim
   creation, or auto-bootstrapped from a document's extracted description) is
   split into `ClaimNarrative` chunks, each embedded via `ai.generate_embedding`
   and upserted into the `claim_narratives` search index.
3. **Generate summary**: `POST /api/claims/{id}/generate-summary/` embeds the
   claim's combined narrative, searches the index for similar claims
   (excluding itself), and calls `ai.chat_completion` to produce a
   `ClaimSummary`. If any similar claim's cosine similarity score exceeds
   `SIMILARITY_FLAG_THRESHOLD` (0.92), the summary is flagged for review.

## Permissions

- `adjuster`: can create claims and process their own claims (upload
  documents, generate summaries, change status) -- queryset-scoped to claims
  they submitted.
- `admin`: sees and can edit every claim, is the only role allowed to delete
  a claim or change a claim's status once it has been `denied`.

## API surface

- `/api/auth/register/`, `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`
- `/api/claims/` (list/create), `/api/claims/{id}/` (retrieve/update/delete)
- `/api/claims/{id}/documents/` (GET list / POST upload)
- `/api/claims/{id}/generate-summary/` (POST)
- `/api/claims/{id}/summary/` (GET)

## Key implementation decisions

- Adjuster queryset scoping is "own claims only" (a personal working queue);
  admins see the whole system. This is enforced in `ClaimViewSet.get_queryset`,
  not just hidden in the serializer.
- The seed data migration (`apps/claims/migrations/0003_seed_data.py`) reuses
  the real `apps/common` modules directly (not mocks), so seeded extracted
  fields, embeddings, and AI summaries are produced by the exact same code
  path as the live API, just running once at migrate time.
- `manage.py test` runs this seed migration too (Django always migrates the
  test database), so the test database starts with the same 8 demo claims
  as dev -- tests that check adjuster-only visibility or create their own
  claims use distinct policy numbers/emails to avoid collisions.

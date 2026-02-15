# ETL Docs - Technical Specs

## Identity
- Service name: `etl-docs`
- Path: `services/etl-docs`
- API prefix: `/documents`

## Runtime
- API container: `etl-docs`
- Worker container: `etl-docs-worker`
- Queue: `docs` (Redis RQ)
- Redis URL: `redis://redis:6379/0`

## Endpoints
- `POST /documents/upload`
- `GET /documents/list/{client_id}`
- `GET /documents/jobs/{job_id}`
- `DELETE /documents/{client_id}/{content_id}`
- `DELETE /documents/client/{client_id}`

## Ingestion Contract
- Required form fields:
- `file` (PDF)
- `client_id` (UUID)
- Optional:
- `content_id` (generated if absent)
- `access_level` (`private|shared|public`)
- `category` (string)

## Processing
- Text extraction: `pypdf`
- OCR fallback: `pdf2image + pytesseract`
- Embeddings: Google Gemini model via `EMBEDDING_MODEL`
- Idempotency: hash-based
- Post-mutation memory reset:
  - On `SYNCED`, `DELETE /documents/{client_id}/{content_id}`, and `DELETE /documents/client/{client_id}` the service performs a best-effort call to `MEMORY_RESET_URL`.
  - Optional auth header via `INTERNAL_API_TOKEN`.

## Storage
- Staging path: `PATH_STAGING`
- Storage path: `PATH_STORAGE`
- Metadata: Postgres (`ai_knowledge_documents`)
- Vectors: Postgres/pgvector (`ai_vectors`)

## External Exposure
- Public/internal URL must be resolved through `ETL_SERVICE_URL` from callers.
- `admin-console-api` must consume ETL through `ETL_SERVICE_URL` only.

## Tests
- Path: `services/etl-docs/tests/`
- Unit + integration:
  - `docker compose exec -T etl-docs pip install --no-cache-dir -r requirements-dev.txt`
  - `docker compose exec -T etl-docs pytest -q tests`
- Smoke:
  - `docker compose exec -T etl-docs python tests/smoke/test_smoke_etl_docs.py`

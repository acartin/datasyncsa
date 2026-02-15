# ETL Docs Tests

Reusable automated checks for `services/etl-docs`.

Includes tenant-isolation coverage in:
`tests/integration/test_tenant_isolation.py`

## Run Unit/Integration Tests
From repository root:

```bash
docker compose exec -T etl-docs pip install --no-cache-dir -r requirements-dev.txt
docker compose exec -T etl-docs pytest -q tests
```

## Reusable Smoke Test
Script:

`services/etl-docs/tests/smoke/test_smoke_etl_docs.py`

Run:

```bash
docker compose exec -T etl-docs python tests/smoke/test_smoke_etl_docs.py
```

Optional env vars:
- `BASE_URL` default `http://127.0.0.1:8000`

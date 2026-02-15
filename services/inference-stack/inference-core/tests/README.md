# Inference Core Tests

Reusable automated checks for `services/inference-stack/inference-core`.

Includes tenant-isolation coverage in:
`tests/integration/test_tenant_isolation.py`

## Run Unit Tests
From repository root:

```bash
docker compose exec -T inference-core pip install --no-cache-dir -r requirements-dev.txt
docker compose exec -T inference-core pytest -q tests
```

## Reusable Smoke Test
Script:

`services/inference-stack/inference-core/tests/smoke/test_smoke_chat.py`

Run:

```bash
docker compose exec -T inference-core python tests/smoke/test_smoke_chat.py
```

Optional env vars:
- `BASE_URL` default `http://127.0.0.1:8003`
- `CLIENT_ID` default `64f357a0-98eb-44f1-9f41-6e615ed26180`

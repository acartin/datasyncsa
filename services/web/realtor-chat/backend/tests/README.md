# Realtor Chat Backend Tests

Reusable automated checks for `services/web/realtor-chat/backend`.

Includes tenant-isolation coverage in:
`tests/integration/test_tenant_isolation.py`

## Run Unit Tests
From repository root:

```bash
docker compose exec -T realtor-api pip install --no-cache-dir -r requirements-dev.txt
docker compose exec -T realtor-api pytest -q tests
```

## Reusable Smoke Test
Script:

`services/web/realtor-chat/backend/tests/smoke/test_smoke_bridge.py`

Proxy smoke (UI nginx -> /api -> bridge):

`services/web/realtor-chat/backend/tests/smoke/test_smoke_web_proxy.py`

Run:

```bash
docker compose exec -T realtor-api python tests/smoke/test_smoke_bridge.py
docker compose exec -T realtor-api python tests/smoke/test_smoke_web_proxy.py
```

Optional env vars:
- `BASE_URL` default `http://127.0.0.1:8000`
- `CLIENT_ID` default `64f357a0-98eb-44f1-9f41-6e615ed26180`

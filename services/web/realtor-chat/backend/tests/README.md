# Realtor Chat Backend Tests

Reusable automated checks for `services/web/realtor-chat/backend`.

## Run Unit Tests
From repository root:

```bash
docker compose exec -T realtor-api pip install --no-cache-dir -r requirements-dev.txt
docker compose exec -T realtor-api pytest -q tests
```

## Reusable Smoke Test
Script:

`services/web/realtor-chat/backend/scripts/smoke_bridge.py`

Run:

```bash
docker compose exec -T realtor-api python scripts/smoke_bridge.py
```

Optional env vars:
- `BASE_URL` default `http://127.0.0.1:8000`
- `CLIENT_ID` default `64f357a0-98eb-44f1-9f41-6e615ed26180`

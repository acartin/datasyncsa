# Semantic Adapter Tests

Reusable automated checks for `services/inference-stack/semantic-adapter`.

## Run Unit Tests
From repository root:

```bash
docker compose exec -T semantic-adapter pip install --no-cache-dir -r requirements-dev.txt
docker compose exec -T semantic-adapter pytest -q tests
```

## Reusable Smoke Test
Script:

`services/inference-stack/semantic-adapter/scripts/smoke_search.py`

Run:

```bash
docker compose exec -T semantic-adapter python scripts/smoke_search.py
```

Optional env vars:
- `BASE_URL` default `http://127.0.0.1:8000`
- `CLIENT_ID` default `64f357a0-98eb-44f1-9f41-6e615ed26180`

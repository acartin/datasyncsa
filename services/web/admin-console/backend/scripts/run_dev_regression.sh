#!/usr/bin/env bash
set -euo pipefail

SERVICE="admin-console-api"

printf '\n[1/3] Checking test dependencies...\n'
if docker compose exec -T "$SERVICE" python -c "import pytest" >/dev/null 2>&1; then
  printf 'pytest is already available in container image. Skipping install.\n'
else
  printf 'pytest not found. Installing dev dependencies...\n'
  docker compose exec -T "$SERVICE" pip install --no-cache-dir -r requirements-dev.txt
fi

printf '\n[2/3] Running unit tests...\n'
docker compose exec -T "$SERVICE" pytest -q tests

printf '\n[3/3] Running tenant isolation smoke...\n'
docker compose exec -T "$SERVICE" python tests/smoke/test_smoke_tenant_isolation.py

printf '\nRegression run completed successfully.\n'

# Admin Console Backend Tests

This folder contains reusable automated checks for `services/web/admin-console/backend`.

## Test Files
- `tests/integration/test_security_and_scoping.py`
  - Verifies protected routes require auth.
  - Verifies lead-detail handler forwards tenant/user scope to service layer.
- `tests/contract/test_sdui_contract.py`
  - Verifies shared SDUI helpers produce stable action contracts (`action_url`, `schema`, `modal_title`, etc.).
  - Verifies `encode_schema_b64` roundtrip for schema payloads.
- `tests/contract/test_sdui_router_contracts.py`
  - Verifies SDUI response contract for critical modules: `users`, `roles`, `prompts`, `clients`.
  - Verifies role-based view switching in `/clients` (superadmin grid vs client-admin dashboard).

## Run Unit Tests
From repository root:

```bash
docker compose exec -T admin-console-api pip install --no-cache-dir -r requirements-dev.txt
docker compose exec -T admin-console-api pytest -q tests
```

## Reusable Smoke Test
Use:

`backend/tests/smoke/test_smoke_tenant_isolation.py`

`backend/tests/smoke/test_smoke_system_user_menu.py`

Run from container:

```bash
docker compose exec -T admin-console-api python tests/smoke/test_smoke_tenant_isolation.py
docker compose exec -T admin-console-api python tests/smoke/test_smoke_system_user_menu.py
```

Environment variables supported by the script:
- `BASE_URL` default `http://127.0.0.1:8000`
- `SUPERADMIN_EMAIL` default `acartina15@hotmail.com`
- `SUPERADMIN_PASSWORD` default `Techimi.15`
- `COCA_ADMIN_EMAIL` default `cocacola-admin@cocacola.com`
- `COCA_ADMIN_PASSWORD` default `holalola`
- `PEPSI_ADMIN_EMAIL` default `pepsi-admin@pepsi.com`
- `PEPSI_ADMIN_PASSWORD` default `holalola`
- `SYSTEM_USER_EMAIL` required for `test_smoke_system_user_menu.py`
- `SYSTEM_USER_PASSWORD` required for `test_smoke_system_user_menu.py`
- `EXPECTED_MENU_LINKS` optional comma-separated list for strict menu assertions (example: `/base,/system/users`)

## One-command Dev Regression
- Script: `backend/scripts/run_dev_regression.sh`
- Runs in sequence:
  - verify `pytest` availability (installs only if missing)
  - `pytest -q tests`
  - tenant isolation smoke

## Dev-Test Container Mode
- `admin-console-api` image now supports build arg `INSTALL_DEV_DEPS` in `Dockerfile`.
- In current `docker-compose.yml`, this arg is set to `"true"` for `admin-console-api`, so `pytest` is baked into the image after rebuild.

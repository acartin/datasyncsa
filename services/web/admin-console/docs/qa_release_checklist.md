# QA Release Checklist - admin-console

## 1. Preparacion de entorno
- Confirmar variables de entorno requeridas en `.env` (`POSTGRES_*`, `JWT_SECRET`, `SYSTEM_ADMIN_EMAIL`, `SYSTEM_ADMIN_PASSWORD`).
- Levantar servicios:
  - `docker compose up -d admin-console-api admin-console-web`
- Verificar salud:
  - `docker compose ps admin-console-api admin-console-web`

## 2. Pruebas backend (bloqueantes)
- Instalar dependencias de test:
  - `docker compose exec -T admin-console-api pip install --no-cache-dir -r requirements-dev.txt`
- Correr unit tests:
  - `docker compose exec -T admin-console-api pytest -q tests`
- Resultado esperado: todos los tests en estado PASS.

## 3. Smoke de aislamiento tenant (bloqueante)
- Ejecutar:
  - `docker compose exec -T admin-console-api python scripts/smoke_tenant_isolation.py`
- Validar:
  - Login de superadmin y admins de tenant responde `200`.
  - Endpoints devuelven solo datos del tenant autenticado.

## 4. Contrato SDUI (backend -> frontend)
- Revisar pantallas clave (`clients`, `users`, `roles`, `prompts`) y confirmar que acciones funcionen con contratos:
  - `url` o `action_url`.
  - `schema` en base64 o JSON serializable.
- Validar create/edit/delete desde grillas.

## 5. Validacion UI operativa
- Login con usuario valido y navegacion por sidebar sin errores JS.
- Tablas con filtros, ordenamiento y paginacion operativos.
- Formularios modales crean/actualizan registros y refrescan grillas.

## 6. Evidencia minima para release
- Guardar salida de:
  - `pytest -q tests`
  - `python scripts/smoke_tenant_isolation.py`
- Registrar hash/fecha de imagen desplegada en QA.

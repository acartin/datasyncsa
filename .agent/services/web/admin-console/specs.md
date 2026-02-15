# ESPECIFICACIÓN MAESTRA WEB admin console siguiendo paradigma server driven ui

## 1. MISIÓN Y PROPÓSITO
La capa web es estrictamente operacional. Prohibida la lógica creativa o heurística. El objetivo es baja latencia y ejecución determinista.

## 2. PRINCIPIOS ESTRUCTURALES
- **Backend Soberano:** El frontend es un terminal tonto (dumb terminal). No decide, solo obedece contratos.
- **Multitenancy Explícito:** El `cliente_id` es obligatorio en toda transacción y consulta SQL.
- **Seguridad Determinista:** Autorización binaria (Permitido/Denegado) resuelta siempre en Backend.

## 3. CAPA DE ACCESO A DATOS (DAL)
- **Cero ORM:** Prohibido el uso de abstracciones mágicas. Solo SQL explícito.
- **Lectura/Escritura Separada:** Uso de vistas SQL (`v_leads_grid`) para optimizar la lectura densa de datos.

## 4. CONTRATOS Y UI-GUARD
- Toda comunicación se valida mediante Pydantic v2.
- Si un componente no está en el catálogo, el backend lo elimina del JSON antes de enviarlo.

## 5. SISTEMA DE UI Y TEMA VELZON
- **UI Declarativa:** La interfaz se define como un árbol JSON.
- **Tokens de Diseño:** Uso obligatorio de tokens: primary, success, danger, warning, info.
- **Layouts:** Uso de sistema de 12 columnas basado en Velzon.
- **Catálogo Cerrado:** Solo se permiten componentes validados (card-metric, grid-visual, form-container, etc.).

## 6. PROHIBICIONES EXPLÍCITAS
- No lógica de negocio en Frontend.
- No consultas directas a tablas desde la UI.
- No estilos CSS ad-hoc.
- No saltarse la validación de cliente_id.

## 7. REGRESIÓN Y VALIDACIÓN (REUTILIZABLE)
- **Unit Tests Backend (reutilizable):**
  - Ruta: `services/web/admin-console/backend/tests/`
  - Comando:
    - `docker compose exec -T admin-console-api pip install --no-cache-dir -r requirements-dev.txt`
    - `docker compose exec -T admin-console-api pytest -q tests`
- **Smoke Test de Aislamiento Tenant (reutilizable):**
  - Script: `services/web/admin-console/backend/tests/smoke/test_smoke_tenant_isolation.py`
  - Comando:
    - `docker compose exec -T admin-console-api python tests/smoke/test_smoke_tenant_isolation.py`
- **Referencia rápida de ejecución:**
  - `services/web/admin-console/backend/tests/README.md`

## 8. REORGANIZACIÓN ESTRUCTURAL (FASE 1 COMPLETADA)
- **Legacy removido**:
  - Eliminados `*_Old` dashboards y archivos `*.bak` del backend.
- **Scripts operativos centralizados**:
  - Ruta: `services/web/admin-console/backend/scripts/`
  - Incluye utilidades de diagnóstico y mantenimiento (`check_hash_config.py`, `restore_pass.py`, `verify_password_change.py`).
- **Duplicidad SDUI reducida**:
  - Helpers compartidos en `services/web/admin-console/backend/app/modules/shared/sdui.py`.
  - Routers refactorizados para reutilizar helpers: `users/router.py`, `roles/router.py`.

## 9. REORGANIZACIÓN ESTRUCTURAL (FASE 2 COMPLETADA)
- **Normalización de nombres de módulos**:
  - `app/modules/_shared` renombrado a `app/modules/shared`.
- **Reducción adicional de duplicidad SDUI**:
  - `prompts/router.py` refactorizado para usar helpers compartidos de acciones y schema.
  - `clients/router.py` con `CLIENT_FORM_FIELDS` reutilizable para evitar duplicación de formulario.
- **Configuración frontend menos acoplada a puerto fijo**:
  - `frontend/config.js` permite override runtime por `localStorage['admin_api_port']`.
  - Fallback conserva puerto `8084`.

## 10. REORGANIZACIÓN ESTRUCTURAL (FASE 3 COMPLETADA)
- **Contrato SDUI unificado en frontend**:
  - Helper central: `frontend/renderer/engine/actionContract.js`.
  - Estandariza resolución de `url/action_url` y serialización de `schema`.
- **Motores de grilla alineados al mismo contrato**:
  - Refactor aplicado en `GridBase.js`, `TableGrid.js`, `GridFilters.js`.
  - Elimina lógica duplicada de placeholders y fallback de schema.
- **Compatibilidad de formularios declarativos**:
  - `FormContainer.js` acepta `action_url` y `url` para migraciones graduales.
- **Checklist de salida a QA documentada**:
  - `services/web/admin-console/docs/qa_release_checklist.md`.

## 11. REGRESIÓN DEV AMPLIADA (FASE ACTUAL)
- **Cobertura de contrato SDUI extendida**:
  - Nuevos tests para módulos críticos adicionales:
    - `tests/contract/test_sdui_router_contracts.py` (`users`, `roles`, `prompts`, `clients`)
    - `tests/contract/test_leads_ai_library_contracts.py` (`leads`, `ai-library`)
- **Ejecución unificada de regresión en desarrollo**:
  - Script: `services/web/admin-console/backend/scripts/run_dev_regression.sh`
  - Verifica `pytest` y solo instala deps de test si faltan; luego ejecuta `pytest -q tests` y `tests/smoke/test_smoke_tenant_isolation.py`.
- **Contenedor dev-test estabilizado**:
  - `services/web/admin-console/backend/Dockerfile` soporta `ARG INSTALL_DEV_DEPS`.
  - `docker-compose.yml` activa `INSTALL_DEV_DEPS: "true"` para `admin-console-api`.

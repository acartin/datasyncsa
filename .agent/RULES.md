# RULES

## 1. Fuente de Verdad de Contexto

Orden obligatorio de lectura para cualquier IA o colaborador:

1. `.agent/RULES.md` (este archivo)
2. `.agent/BRAIN_MAP.md` (arquitectura y mapa operativo)
3. `.agent/AI_CONTEXT_PACK.md` (snapshot técnico generado)

Si hay contradicción:
- Prevalece el código ejecutable del repo.
- Luego `.agent/RULES.md`.
- Luego `.agent/BRAIN_MAP.md`.
- Luego `.agent/AI_CONTEXT_PACK.md`.

## 2. Scope por Servicio (no mezclar patrones)

Servicios activos principales:
- `services/web/admin-console`
- `services/web/realtor-chat`
- `services/inference-stack/inference-core`
- `services/inference-stack/semantic-adapter`
- `services/inference-stack-v2/inference-core-v2`
- `services/etl-docs`

Servicios deprecados:
- `services/etl-processor`
- `services/legacy-ETL_DOCS`
- `services/inference-stack__reference_disabled`

Regla:
- No implementar features nuevas en servicios deprecados.
- No copiar patrones legacy a servicios activos.

## 3. Arquitectura Innegociable

- Backend soberano: frontend renderiza contratos, no decide negocio.
- SDUI/SUID: la UI se entrega como JSON (`layout`, `components`, `properties`).
- El backend nunca debe responder HTML para vistas operativas SDUI.
- `main.py` de cada API debe ser mínimo: app init, middleware, `include_router`.

## 4. Multi-Tenant y Seguridad

- Toda consulta de datos operativa debe tener scope de tenant (`client_id` o equivalente de seguridad).
- Nunca exponer data cross-tenant por ausencia de filtro.
- Autorización por backend (JWT/dependencies/RoleChecker). Nunca por lógica de frontend.
- No confiar en `localStorage` para identidad/autorización.
- Todo endpoint interno sensible debe validar token interno cuando aplique (`INTERNAL_API_TOKEN`).

## 5. DAL y Acceso a Datos

- Priorizar SQL explícito (`sqlalchemy.text()` / SQL raw) en módulos operativos.
- Evitar magia de ORM en caminos críticos de lectura/escritura.
- Evitar patrones N+1 en grids; preferir consultas agregadas/vistas.
- Mantener payloads de salida compactos, sin metadata innecesaria.

## 6. Reglas SDUI

- Contratos se validan con Pydantic.
- Si un componente no está soportado por el renderer, no debe salir en payload final.
- Mantener consistencia de acciones SDUI (`action_url`/`url`, `schema`, `modal_title`) según helpers compartidos.
- Evitar estilos ad-hoc cuando el sistema ya tiene componentes/tokens declarativos.

## 7. Infra y Operación

- Orquestación oficial: `docker-compose.yml` en raíz.
- ETL externo para admin-console: `ETL_SERVICE_URL` es obligatorio (sin fallback local).
- Storage documental:
  - mount R2 vía `rclone-mount.service`
  - ruta host: `/srv/datasyncsa/volumes/r2_storage`
- No cambiar puertos/URLs base sin ajustar `docker-compose.yml` y `.env.example`.
- Credenciales de base de datos:
  - Prohibido hardcodear credenciales en código o scripts.
  - Toda conexión DB debe resolverse por variables de entorno (`DATABASE_URL` o `DB_USER`/`DB_PASS`/`DB_NAME`/`DB_PORT`).
  - `.env.example` es la referencia contractual de variables requeridas.

## 8. IA e Inference

- `inference-core` v1: chat RAG legacy + scoring legacy.
- `inference-core-v2`: scoring por vertical/modelo/prompt versionado.
- No asumir que `lead_type` viene del cliente en v2; se resuelve por vertical del tenant.
- Mutaciones de conocimiento (ETL sync/delete) deben disparar reset de memoria best-effort.

## 9. Testing Mínimo por Cambio

Si tocas cada área, corre como mínimo:

Admin Console backend:
- `docker compose exec -T admin-console-api pytest -q tests`

Realtor Chat backend:
- `docker compose exec -T realtor-api pytest -q tests`

Inference Core v1:
- `docker compose exec -T inference-core pytest -q tests`

Semantic Adapter:
- `docker compose exec -T semantic-adapter pytest -q tests`

Inference Core v2:
- `docker compose exec -T inference-core-v2 env PYTHONPATH=/app pytest -q tests`

ETL Docs:
- `docker compose exec -T etl-docs pytest -q tests`

Si no se ejecutan pruebas:
- documentar explícitamente qué no se validó y por qué.

## 10. Checklist de Rechazo Inmediato

Rechazar cambios que incurran en alguno:

- Rompen aislamiento tenant.
- Saltan validación de contratos Pydantic.
- Mueven lógica de negocio al frontend.
- Introducen endpoints HTML en flujos SDUI.
- Implementan features nuevas en servicios deprecados.
- Eliminan validaciones de seguridad para rutas sensibles.
- Rompen integración ETL externa obligatoria.

## 11. Convención de Trabajo con IA

Antes de pedir cambios grandes:

1. Regenerar contexto: `bash .agent/regenerar_contexto.sh`
2. Verificar que `.agent/BRAIN_MAP.md` esté actualizado.
3. Entregar a la IA: `.agent/RULES.md` + `.agent/BRAIN_MAP.md` + `.agent/AI_CONTEXT_PACK.md`.

Para tareas de alto impacto, incluir además:
- archivo objetivo
- restricción explícita de no tocar módulos fuera de scope
- suite de test mínima esperada

## 12. Estado de Migración desde .agent

`.agent` se considera contexto legacy difícil de mantener.

Nuevo baseline operativo:
- `.agent/RULES.md` (reglas vivas)
- `.agent/BRAIN_MAP.md` (arquitectura viva)
- `.agent/AI_CONTEXT_PACK.md` (snapshot técnico regenerable)

# RULES

## 1. Fuente de Verdad de Contexto

Precondición obligatoria al iniciar **cada nueva sesión** (humano o IA):

1. Carga base obligatoria (siempre):
   - Leer `.agent/RULES.md` (este archivo)
   - Leer `.agent/PY_EXECUTION_MAP.md` (host vs contenedor por ruta)
2. Determinar si se requiere regeneración de contexto:
   - Si no existe `.agent/BRAIN_MAP.md` o `.agent/AI_CONTEXT_PACK.md`
   - Si el commit actual difiere del commit registrado en `.agent/BRAIN_MAP.md`
   - Si el usuario pide actualización completa de contexto
   - Si hubo incidente operativo y se requiere foto técnica fresca
3. Solo si aplica el punto 2, ejecutar `bash .agent/regenerar_contexto.sh`
4. Si se regeneró, confirmar actualización de:
   - `.agent/BRAIN_MAP.md`
   - `.agent/AI_CONTEXT_PACK.md`
5. Recién después iniciar análisis/implementación.
6. Preflight obligatorio de entorno para tareas con DB/Docker:
   - Validar variables críticas (`DB_USER`, `DB_NAME`, `DATABASE_URL`) sin volcar secretos.
   - Prohibido hacer `cat .env` completo salvo instrucción explícita del usuario.
   - Para comandos SQL/DB en shell, usar wrapper:
     `set -a; source .env; set +a; <comando>`
   - Si falta una variable crítica, detener ejecución y reportar antes de continuar.

Orden obligatorio de lectura (carga mínima primero):

1. `.agent/RULES.md`
2. `.agent/PY_EXECUTION_MAP.md`
3. `.agent/BRAIN_MAP.md` (lectura breve: encabezado + mapa operativo)
4. `.agent/AI_CONTEXT_PACK.md` (lectura selectiva por secciones, solo on-demand)

Regla de eficiencia de contexto:
- `AI_CONTEXT_PACK.md` es archivo de consulta, no de lectura completa por defecto.
- Evitar `cat` completo de archivos grandes; priorizar `rg`, `sed -n`, `find` por sección puntual.

Si hay contradicción:
- Prevalece el código ejecutable del repo.
- Luego `.agent/RULES.md`.
- Luego `.agent/PY_EXECUTION_MAP.md`.
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

Regla crítica de sincronización runtime (obligatoria para Inference v2):
- Si se modifica cualquier archivo de `services/inference-stack-v2/inference-core-v2/**`, es obligatorio ejecutar antes de probar:
  - `docker compose up -d --build inference-core-v2 inference-core-v2-worker`
- Motivo: en `docker-compose.yml` esos servicios no montan el código de `/app` por volumen, solo `schemas`; sin rebuild quedan ejecutando imagen vieja.
- No se aceptan resultados de tests/simulaciones si no se recrearon ambos contenedores (`inference-core-v2` + `inference-core-v2-worker`) después del cambio.
- Verificación mínima obligatoria:
  - `docker compose ps inference-core-v2 inference-core-v2-worker`
  - `docker compose exec -T inference-core-v2-worker /bin/bash -lc "grep -n 'deterministic_scoring_service' app/services/scoring_engine.py"`

Si tocas cada área, corre como mínimo en el contenedor **backend/API** correspondiente (nunca en `*-web`):

Admin Console backend (`admin-console-api`):
- `docker compose exec -T admin-console-api pytest -q tests`

Realtor Chat backend (`realtor-api`):
- `docker compose exec -T realtor-api pytest -q tests`
- si `pytest` no está instalado en la imagen: `docker compose exec -T realtor-api pip install -r /app/requirements-dev.txt`

Inference Core v2 (`inference-core-v2`):
- `docker compose exec -T inference-core-v2 env PYTHONPATH=/app pytest -q tests`

Semantic Adapter v2 (`semantic-adapter-v2`):
- `docker compose exec -T semantic-adapter-v2 pytest -q tests`

ETL Docs (`etl-docs`):
- `docker compose exec -T etl-docs pytest -q tests`

Inference Core v1 (`inference-core`, solo si ese servicio existe en el compose activo):
- `docker compose exec -T inference-core pytest -q tests`

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

Antes de empezar cualquier trabajo en una nueva sesión:

1. Aplicar el protocolo de la sección 1 (sin duplicar pasos).
2. Entregar como contexto base: `.agent/RULES.md` + `.agent/PY_EXECUTION_MAP.md`.
3. Entregar `.agent/BRAIN_MAP.md` y `.agent/AI_CONTEXT_PACK.md` solo según necesidad de la tarea.

Regla:
- No arrancar implementación, debugging ni code review sin haber ejecutado los pasos 1-2 en esa sesión.
- Excepción permitida: incidente operativo urgente; regularizar la regeneración al cierre y dejar constancia.
- En tareas de reorganización/documentación de tests:
  - Validar solo con `--help`/`--list` y `python3 -m py_compile`.
  - No ejecutar `pytest` en host salvo instrucción explícita del usuario.
  - Para pruebas reales, ejecutar en el contenedor mapeado del servicio.

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
- `.agent/PY_EXECUTION_MAP.md` (mapeo operativo de ejecución Python por ruta)

## 13. Presupuesto de Contexto (anti-compactación)

Objetivo:
- Minimizar tokens de contexto y evitar compactación automática por sobrecarga.

Política:
- Onboarding de sesión: cargar completo solo `RULES.md` y `PY_EXECUTION_MAP.md`.
- `BRAIN_MAP.md`: leer resumen operativo, no volcado completo salvo necesidad real.
- `AI_CONTEXT_PACK.md`: consultar secciones específicas, nunca como carga masiva por defecto.
- Si una consulta no requiere arquitectura/infra completa, no abrir archivos de snapshot.

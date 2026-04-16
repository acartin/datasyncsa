# RULES

## 1. Fuente de Verdad de Contexto

Precondicion obligatoria al iniciar cada nueva sesion:

1. Carga base obligatoria:
   - Leer `.agent/RULES.md`
   - Leer `.agent/PY_EXECUTION_MAP.md`
   - Leer `.agent/ACTIVE_DB_PROMPTS.md`
2. Determinar si se requiere regeneracion de contexto:
   - falta `.agent/BRAIN_MAP.md`, `.agent/AI_CONTEXT_PACK.md` o `.agent/ACTIVE_DB_PROMPTS.md`
   - el commit actual difiere del commit registrado en `.agent/BRAIN_MAP.md`
   - el usuario pide actualizacion completa de contexto
   - hubo un cambio grande de arquitectura o compose
3. Solo si aplica el punto 2, ejecutar `bash .agent/regenerar_contexto.sh`
4. Recién despues iniciar implementacion, debug o review

Preflight obligatorio para tareas con DB/Docker:

- Validar variables criticas (`DB_USER`, `DB_NAME`, `DATABASE_URL`) sin volcar secretos
- Prohibido hacer `cat .env` completo salvo instruccion explicita del usuario
- Para comandos SQL/DB en shell, usar wrapper:
  `set -a; source .env; set +a; <comando>`
- Si falta una variable critica, detener ejecucion y reportar

Orden recomendado de lectura:

1. `.agent/RULES.md`
2. `.agent/PY_EXECUTION_MAP.md`
3. `.agent/ACTIVE_DB_PROMPTS.md`
4. `.agent/BRAIN_MAP.md` solo encabezado + mapa operativo
5. `.agent/AI_CONTEXT_PACK.md` solo secciones necesarias

Para tareas del stack conversacional actual:

6. `.agent/AI_RUNTIME_BOOTSTRAP.md`
7. `docs/AI_RUNTIME_PROMPT_RUNTIME.md`
8. `services/ai_runtime/ARCHITECTURE.md`
9. `docs/AI_RUNTIME_INDEX.md`

Regla especial para prompts de BD:

- `.agent/ACTIVE_DB_PROMPTS.md` es el snapshot operativo local de prompts externos al repo.
- Si la tarea toca `realtor`, lead capture, scoring, `slot_hints`, appointment intent/type o policy conversacional, refrescar ese archivo una vez por sesion con:
  `bash .agent/refresh_db_prompts.sh`
- Si el refresh falla pero existe `.agent/ACTIVE_DB_PROMPTS.md`, trabajar con ese snapshot cacheado y reportar explicitamente que no se pudo verificar frescura en BD.
- Si el refresh falla y no existe `.agent/ACTIVE_DB_PROMPTS.md`, detener implementacion/review y reportar bloqueo.

Para tareas que toquen logica conversacional, prompting por vertical, lead capture, scoring o recomendaciones de arquitectura en `ai-runtime`:

- No basta con leer donde viven los prompts.
- Es obligatorio leer los prompts activos del tenant en BD o en trazas equivalentes y mantenerlos presentes en el contexto de trabajo antes de recomendar cambios.
- Minimo obligatorio:
  - `lead_ai_prompts.slug = 'primary_chat'` para `tone_prompt`
  - prompts activos en codigo del vertical relevante (`analyze_turn`, `intent_detector`, `synthesis_prompt`)
  - si la tarea toca scoring o lead capture: `lead_scoring_prompts.prompt_template` y `extraction_schema`
- Para `realtor`, lead capture o scoring, tambien es obligatorio leer el snapshot `lead_scoring_prompts.id = '190dc860-9d37-4883-a6f4-c3019fdd882e'` desde `.agent/ACTIVE_DB_PROMPTS.md` o recargarlo desde BD en la sesion actual.
- Si no se pudieron leer los prompts activos, no proponer cambios de politica conversacional como si fueran hechos; reportar el bloqueo y limitarse a bugs/guardrails duros.
- Precedencia obligatoria para phrasing de captura:
  - `slot_hints.question` del prompt activo
  - luego `lead_scoring_prompts.extraction_schema.fields[].question`
  - luego fallback minimo en Python
- `fields[].question` es wording base configurable por tenant/modelo; no sustituye la decision semantica del LLM sobre si conviene preguntar o no.

Regla de precedencia:

1. Codigo ejecutable vigente
2. `.agent/RULES.md`
3. `.agent/PY_EXECUTION_MAP.md`
4. `.agent/ACTIVE_DB_PROMPTS.md` o lectura fresca equivalente desde BD
5. `.agent/BRAIN_MAP.md`
6. `.agent/AI_CONTEXT_PACK.md`

## 2. Scope por Servicio

Servicios activos principales:

- `services/ai_runtime`
- `services/scoring-core`
- `services/web/chat-web-renderer`
- `services/web/admin-console`
- `services/etl-docs`
- `services/data`
- `services/shared`

Servicios de apoyo o exploracion:

- `services/ai-agents` no es parte del runtime operativo actual

Servicios legacy o deprecados:

- `services/legacy/agent-core`
- `services/legacy/inference-stack-v2`
- `services/etl-processor`

Reglas:

- No implementar features nuevas en servicios legacy salvo instruccion explicita
- No copiar patrones legacy a `ai-runtime`
- Usar `services/legacy/agent-core` y `services/legacy/inference-stack-v2` solo como referencia historica cuando sea necesario

## 3. Arquitectura Innegociable

- `ai-runtime` es el unico cerebro conversacional operativo
- `chat-web-renderer` transforma la respuesta del runtime a SDUI para el canal web
- `scoring-core` es un bounded context separado; no absorbe decision conversacional
- `main.py` de cada API debe ser minimo: app init, middleware, `include_router`

## 4. Multi-Tenant y Seguridad

- Toda operacion conversacional debe venir con `client_id`
- Toda consulta operativa debe tener scope tenant
- Redis debe usar llaves prefijadas por tenant
- Nunca exponer datos cross-tenant por ausencia de filtro
- Todo endpoint interno sensible debe validar `INTERNAL_API_TOKEN` cuando aplique
- No confiar en frontend o `localStorage` para identidad/autorizacion

## 5. DAL y Acceso a Datos

- Priorizar SQL explicito en rutas operativas
- Evitar magia ORM en caminos criticos
- Evitar N+1 en grids y consultas conversacionales
- Mantener payloads compactos y contratos claros
- `services/data` es la capa compartida del runtime conversacional

## 6. SDUI y Canales

- El backend define negocio y contratos; el frontend solo renderiza
- Los contratos UI se validan con Pydantic
- No devolver HTML en flujos operativos SDUI
- Si un componente no esta soportado por el renderer, no debe salir en payload final

## 7. Runtime Conversacional

- `ai-runtime` resuelve tenant, vertical y flow efectivo
- `realtor_flow` y `basic_flow` son selectores internos del runtime
- El estado se hidrata desde Redis y se persiste por sesion
- `tenant_config` se resuelve al inicio del turno, se reinyecta al estado y se cachea por `client_id`
- La composicion de prompts ocurre en runtime: tone opcional del tenant + prompt vertical + contexto
- `services/data` y `services/ai_runtime/rag/**` deben respetar aislamiento por `client_id`
- Mutaciones de conocimiento deben disparar reset de memoria best-effort contra `ai-runtime`

Regla anti-heuristica:

- Prohibido hardcodear heuristicas de intencion, ubicacion o flujo para suplir planner/routers/config
- Si se necesita fallback, debe ser parametrizable o estar controlado por prompts/config

## 8. Infra y Operacion

- Orquestacion oficial: `docker-compose.yml`
- No cambiar nombres de servicios, puertos o URLs base sin ajustar:
  - `docker-compose.yml`
  - `.env.example`
  - `.agent/*` relevante
- Credenciales y conexiones via variables de entorno; nunca hardcodeadas
- `.env.example` es la referencia contractual de variables requeridas

## 9. Testing Minimo por Cambio

Regla general:

- Si cambias codigo en un servicio Docker que no monta el codigo fuente completo, debes hacer rebuild antes de validar
- No correr `pytest` en host salvo instruccion explicita del usuario
- Si no se ejecutan pruebas, documentar exactamente que no se valido y por que

Minimos por area:

- `services/ai_runtime/**`
  - `docker compose up -d --build ai-runtime`
  - `docker compose exec -T ai-runtime /bin/bash -lc "cd /app/services/ai_runtime && find . -type f -name '*.py' -print0 | xargs -0 python -m py_compile"`
  - `curl -fsS http://127.0.0.1:${AI_RUNTIME_PORT:-8096}/api/v1/health`
- `services/data/**`
  - `docker compose up -d --build ai-runtime`
  - `docker compose exec -T ai-runtime /bin/bash -lc "cd /app && find services/ai_runtime services/data -type f -name '*.py' -print0 | xargs -0 python -m py_compile"`
- `services/web/chat-web-renderer/backend/**`
  - `docker compose up -d --build chat-web-renderer-api`
  - `docker compose exec -T chat-web-renderer-api pytest -q tests`
- `services/web/admin-console/backend/**`
  - `docker compose up -d --build admin-console-api`
  - `docker compose exec -T admin-console-api pytest -q tests`
- `services/scoring-core/**`
  - `docker compose up -d --build scoring-core scoring-core-worker`
  - `docker compose exec -T scoring-core /bin/bash -lc "find . -type f -name '*.py' -print0 | xargs -0 python -m py_compile"`
- `services/etl-docs/**`
  - `docker compose up -d --build etl-docs etl-docs-worker`
  - `docker compose exec -T etl-docs pytest -q tests`

Si cambias `schemas/**`:

- Reiniciar consumidores:
  - `ai-runtime`
  - `scoring-core`
  - `scoring-core-worker`
  - `admin-console-api`
  - `chat-web-renderer-api`
  - `etl-docs`
  - `etl-docs-worker`

## 10. Checklist de Rechazo Inmediato

Rechazar cambios que:

- rompen aislamiento tenant
- mueven negocio al frontend
- introducen features nuevas en servicios legacy
- eliminan validaciones de seguridad
- dejan `.agent` o `.env.example` desalineados despues de cambiar compose/naming
- mezclan scoring conversacional dentro de frontend o componentes legacy

## 11. Convencion de Trabajo con IA

Antes de empezar trabajo nuevo:

1. aplicar la seccion 1
2. usar `.agent/RULES.md` + `.agent/PY_EXECUTION_MAP.md` como base
3. cargar `.agent/ACTIVE_DB_PROMPTS.md`
4. consultar `BRAIN_MAP` y `AI_CONTEXT_PACK` solo lo necesario

En tareas de reorganizacion o documentacion de tests:

- validar con `python3 -m py_compile`, `docker compose config`, `--help` o `--list` cuando baste
- evitar gastar tiempo en suites pesadas si el trabajo no cambia comportamiento

Para tareas de alto impacto, dejar claro:

- archivo objetivo
- servicios afectados
- validacion minima esperada

## Guardrails de Arquitectura para `ai-runtime`

- `shared` solo puede contener infraestructura y piezas tecnicas neutrales. No puede contener semantica, ejemplos, vocabulario ni reglas de negocio de un vertical.
- Todo prompt semantico que interprete negocio es `vertical-owned`. Como minimo, `analyze_turn` e `intent_detector` no pueden depender de prompts shared para semantica de negocio.
- `synthesis_prompt` solo redacta. `lead_scoring_prompts` solo gobierna scoring y estrategia de captura.
- Si un prompt necesita ejemplos, entidades o capacidades del dominio, no pertenece a `_shared/prompts`. La duplicacion consciente por vertical es preferible a una abstraccion shared falsa.
- Cada vertical debe poder agregarse o eliminarse sin romper la composicion semantica de los demas.
- El codigo determinista solo cubre validacion, invariantes, seguridad, side effects y guardrails universales; no debe esconder politica de negocio.
- Si una politica conversacional pasa de prompt/LLM a codigo, debe expresarse como abstraccion semantica de alto nivel y no como casuistica textual. La regla debe nombrar una categoria estable del negocio y cubrir multiples variaciones del lenguaje sin enumerarlas una por una.
- No mezclar en un mismo nodo interpretacion semantica, compilacion de intents, scoring y phrasing final.
- Todo cambio de ownership de prompts o fronteras entre verticales debe quedar protegido por pruebas de composicion y desacople.

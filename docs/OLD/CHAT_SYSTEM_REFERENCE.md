# Chat System Reference

Ultima actualizacion: `2026-03-07`

Este es el documento canonico del sistema de chat en `/srv/datasyncsa`.

Su funcion es describir:
- el objetivo real del sistema,
- la arquitectura viva,
- la autoridad de cada servicio,
- la fuente de verdad por concern,
- el estado actual de migracion,
- y los anti-patrones que no se deben reintroducir.

## 1. Documentos canonicos

Mantener solo esta jerarquia:

1. `docs/CHAT_SYSTEM_REFERENCE.md`
   - referencia operativa viva del sistema actual.

2. `docs/INFERENCE_CORE_V3_BLUEPRINT.md`
   - blueprint arquitectonico objetivo de `inference-core-v3`.

3. `docs/AI_PROMPTS_WAVE2_TOOLS_AGENDA.md`
   - backlog/documento de trabajo para workflow tools futuras.
   - no describe el estado actual; describe la siguiente ola.

## 2. Resumen ejecutivo actual

El sistema ya no debe pensarse como un renderer con inteligencia repartida.

La arquitectura viva correcta es:

- `inference-core-v3` decide el turno.
- `semantic-adapter-v2` recupera contexto vectorial.
- los ejecutores deterministas ejecutan SQL/retrieval/side-effects.
- `chat-web-renderer` solo transporta y renderiza SDUI.
- `generic-bridge-v2` y `property-bridge-v2` son wrappers finos.

`inference-core-v2` ya no es la autoridad del chat en web.
Queda como legado operativo mientras termina la estabilizacion y el retiro parcial.

## 3. Objetivo del sistema

El stack soporta dos familias de conversacion bajo un mismo runtime:

1. `generic`
   - preguntas generales,
   - respuestas informativas,
   - RAG,
   - scoring de lead.

2. `realtor`
   - busqueda de propiedades,
   - inventario,
   - rango de precios,
   - continuidad de filtros,
   - render de tarjetas y componentes de propiedades.

El objetivo arquitectonico es que exista una sola autoridad del turno:

- `inference-core-v3`

## 4. Servicios vivos y responsabilidad real

### 4.1 Agente soberano

- `services/inference-stack-v2/inference-core-v3`
  - runtime soberano del turno.
  - resuelve tenant y vertical desde `client_id`.
  - carga prompts por proposito.
  - monta el tool registry efectivo por tenant.
  - decide `route_mode`, `intent` y `active_subflow`.
  - ejecuta subflujos `realtor` y `generic`.
  - sintetiza la respuesta final.
  - persiste la respuesta final real.
  - encola side-effects como scoring async.

### 4.2 Retrieval

- `services/inference-stack-v2/semantic-adapter-v2`
  - servicio de retrieval semantico/vectorial.
  - no decide copy ni routing.

### 4.3 Canal web

- `services/web/chat-web-renderer/backend`
  - BFF del widget web.
  - mantiene sesion efimera por `client_id + channel + channel_user_id`.
  - reenvia al inference core activo.
  - adapta respuesta canonica a SDUI.
  - no decide intent, no genera SQL y no reescribe negocio.

- `services/web/chat-web-renderer/frontend`
  - widget HTML/JS.
  - conserva `channelUserId` y `conversationId`.
  - renderiza componentes SDUI.
  - expone `New Chat`.

### 4.4 Wrappers de compatibilidad

- `services/generic-bridge-v2`
  - wrapper fino hacia el inference core activo.
  - no contiene logica de negocio.

- `services/property-bridge-v2`
  - wrapper fino para contratos realtor legacy.
  - no es autoridad del turno.

### 4.5 ETL y mantenimiento

- `services/etl-docs`
  - ingesta documental y embeddings.
  - puede solicitar reset interno de memoria cuando aplica.

## 5. Flujo canonico del turno

Secuencia base:

1. el canal recibe el mensaje;
2. el canal adjunta `client_id`, `conversation_id`, `channel`, `channel_user_id` y metadata;
3. el mensaje entra a `inference-core-v3 /api/v3/chat`;
4. `inference-core-v3` carga tenant runtime y estado conversacional;
5. el agente decide si responde directo, usa retrieval, usa SQL realtor o deriva a workflow;
6. el agente sintetiza la respuesta final visible;
7. el core persiste exactamente esa respuesta;
8. el core encola side-effects no bloqueantes;
9. el canal solo renderiza `answer + components`.

Regla critica:

- el canal no piensa despues del core.

## 6. Grafo vivo de `inference-core-v3`

Nodos activos del root graph:

1. `hydrate_request`
2. `load_tenant_runtime`
3. `load_conversation_state`
4. `merge_live_memory`
5. `route_turn`
6. `dispatch_vertical_subflow`
7. `synthesize_final`
8. `persist_final_turn`
9. `enqueue_side_effects`
10. `return_response`

Subflujos hoy operativos:

- `realtor_search`
- `generic_answer`
- `generic_rag`

Subflujo diferido:

- `workflow`
  - calendar/email/MCP todavia no estan integrados con providers reales.

## 7. Fuente de verdad por concern

### 7.1 Conversacion persistente

Fuente de verdad:

- `lead_conversations`

Responsable:

- `inference-core-v3`

Debe contener:

- mensaje real del usuario,
- respuesta final real del asistente,
- snapshot contextual operativo,
- no respuestas tentativas ni intermedias.

### 7.2 Sesion efimera del canal

Fuente de verdad:

- Redis del renderer

Clave canonica:

- `session:{client_id}:{channel}:{channel_user_id}`

Uso:

- conservar `conversation_id`,
- contexto efimero del canal,
- datos UI/transporte.

Esto no reemplaza la conversacion persistida en DB.

### 7.3 Memoria conversacional viva

Fuente de verdad:

- `lead_conversations.context_snapshot`

Estructura base:

```json
{
  "conversation_extraction_result": {
    "common": {},
    "vertical": {}
  },
  "realtor_search_state": {},
  "last_agent_route": {},
  "last_tool_results": {},
  "last_execution_facts": {},
  "last_side_effects": {}
}
```

### 7.4 Prompting

Fuente de verdad:

- `lead_ai_prompts`

Resolucion:

1. prompt por `client_id + slug`
2. fallback global `client_id IS NULL`

Prompts por proposito hoy relevantes:

- `primary_chat`
- `route_turn`
- `generic_planner_system`
- `generic_answer_synthesis`
- `realtor_turn_system`
- `realtor_answer_synthesis`
- `workflow_planner_system`
- `workflow_answer_synthesis`

### 7.5 Scoring

Persistencia operativa:

- `lead_scoring_jobs`
- `lead_scorecards`

El enqueue ocurre desde `inference-core-v3`.
La ejecucion de scoring sigue siendo parte del legado operativo mientras se completa la transicion total.

## 8. Vertical realtor: ownership actual

La autoridad del flujo realtor hoy vive en `inference-core-v3`.

Responsabilidades:

- router/planner del turno:
  - decide si usar SQL, RAG o aclaracion;
- ejecutor SQL:
  - valida seguridad,
  - ejecuta consultas,
  - devuelve facts y componentes;
- synthesis:
  - redacta la respuesta final natural;
- persistencia:
  - guarda exactamente lo mostrado al usuario.

Regla:

- los ejecutores deterministas no redactan copy conversacional.

## 9. Vertical generic: ownership actual

El vertical no-realtor tambien corre ya en `inference-core-v3`.

Responsabilidades:

- responder directo cuando el turno no requiere tools;
- usar retrieval cuando el turno requiere facts documentales;
- sintetizar respuesta final en el agente;
- persistir y encolar scoring igual que realtor.

## 10. Estado actual de migracion

### Ya resuelto

- `chat-web-renderer` apunta a `inference-core-v3`
- `generic-bridge-v2` apunta a `inference-core-v3`
- `property-bridge-v2` apunta a `inference-core-v3`
- `inference-core-v3` ya devuelve `leadId`, `scoringStatus`, `scoringJobId`, `scoringEta`
- `inference-core-v3` expone:
  - `/api/v3/chat`
  - `/api/v3/health`
  - `/api/v3/cache/invalidate`
  - `/api/v3/internal/memory/reset`

### Diferido deliberadamente

- workflow real con:
  - calendar
  - email
  - MCP

Esto se aplaza hasta estabilizar naturalidad y coherencia conversacional.

### Legado que sigue vivo

- `inference-core-v2`
- `inference-core-v2-worker`

No deben seguir absorbiendo inteligencia nueva del chat.

## 11. Anti-patrones prohibidos

- meter logica de negocio en `chat-web-renderer`
- meter heuristica hardcodeada de intent o continuidad
- hacer que un ejecutor redacte copy conversacional
- persistir una respuesta distinta a la que vio el usuario
- crear una segunda fuente de verdad para memoria conversacional
- hacer que bridges reinterpreten el turno
- volver a distribuir inteligencia fuera del agente

## 11.1 Guardrail de Regresion Realtor

La validacion conductual canonica del vertical realtor no vive solo en unit tests.

Script de referencia:

- `tests/sandbox/realtor/realtor_v3_regression_battery.py`

Objetivo:

- detectar regresiones en contratos de conversacion del flujo realtor en `inference-core-v3`

Cobertura principal:

- `search`
- `refine`
- `inventory`
- `price_range`
- preguntas referenciales sobre cards mostradas
- memoria de busqueda y filtros activos
- RAG documental despues de busqueda
- captura progresiva de lead sin friccion

Uso operativo:

```bash
python3 tests/sandbox/realtor/realtor_v3_regression_battery.py \
  --request-timeout 45 \
  --json-out /tmp/realtor_v3_battery.json
```

Salida esperada:

- resumen de escenarios
- numero de `issues`
- reporte JSON consumible para analisis posterior

Regla:

- si se modifica `routing`, `planner`, `answer_synthesizer`, `lead_followup_planner`, contratos de presentacion/grounding o flujo realtor en `inference-core-v3`, esta bateria debe correrse junto con los unit tests del servicio.

## 12. Politica de documentacion

Para mantener la documentacion corta y util:

- `CHAT_SYSTEM_REFERENCE.md`
  - describe el sistema actual

- `INFERENCE_CORE_V3_BLUEPRINT.md`
  - describe la arquitectura objetivo y el plan estructural

- `AI_PROMPTS_WAVE2_TOOLS_AGENDA.md`
  - describe trabajo futuro de workflow

Todo documento que describa una arquitectura ya reemplazada o una instruccion puntual de reingenieria ya completada debe archivarse o eliminarse.

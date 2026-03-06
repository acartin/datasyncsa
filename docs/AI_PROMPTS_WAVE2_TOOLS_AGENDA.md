# Prompts Especificos Wave 2 - Tools + Agenda (Placeholders)

## Objetivo
Definir prompts listos para asignar a diferentes IAs para preparar la integracion de tools (en especial agenda) sin materializar aun la implementacion completa de Google Calendar/Outlook.

## Regla innegociable de contratos
- Carpeta unica de contratos: `/srv/datasyncsa/schemas`
- Ningun contrato nuevo debe vivir dentro de `services/...`
- Los modulos de codigo solo consumen contratos definidos en `/schemas`

## Alcance de Wave 2
- Crear estructura de tools y agenda como placeholders.
- Dejar puntos de extension estables para evitar refactor posterior.
- No integrar aun credenciales reales ni llamadas productivas a Google/Outlook.

## Restricciones globales
1. No romper flujo de chat actual.
2. Feature flags obligatorias para todo lo nuevo.
3. Todo fallback debe degradar a `chat_text`.
4. No usar `user_id` ambiguo; mantener `channel_user_id` y `auth_user_id`.

---

## Prompt IA-W2-01: Contratos de Tools en `/schemas`

```text
Actua como API Contract Engineer. Define contratos JSON versionados para framework de tools y agenda.

Objetivo:
- Crear contratos base en `/srv/datasyncsa/schemas` para tool-calling interno.

Scope permitido:
- /srv/datasyncsa/schemas/
- docs/ (si necesitas notas de version)

Entregables:
1) `schemas/tool_envelope.v1.json`
2) `schemas/tool_agenda.v1.json`
3) `schemas/appointment_negotiation_state.v1.json`

Campos minimos esperados:
- Tool envelope: tool_name, tool_action, tool_input, tool_result, tool_status, tool_trace_id, timestamps.
- Agenda: assigned_contact_id, provider, timezone, availability_slots, selected_slot, booking_status, external_event_id.
- Negociacion: detected, collecting_constraints, proposing_slots, negotiating, confirmed, booked, failed, cancelled.

Restricciones:
- No crear contratos duplicados fuera de `/schemas`.
- No codificar detalles de proveedor real (tokens, endpoints productivos).

DoD:
- JSON valido.
- Versionado claro (`*.v1.json`).
```

---

## Prompt IA-W2-02: Framework de Tools en inference-core-v2

```text
Actua como Backend Platform Engineer. Implementa esqueleto de framework de tools en inference-core-v2.

Objetivo:
- Agregar ToolRegistry + ToolExecutor + interfaz ToolHandler, sin logica de proveedor real.

Scope permitido:
- services/inference-stack-v2/inference-core-v2/app/
- tests del inference-core-v2

Tareas:
1) Crear modulo base de tools:
   - registry
   - executor
   - base handler/interface
2) Integrar hook en el flujo de chat del orchestrator:
   - detectar intencion de agenda (placeholder)
   - invocar executor bajo flag
3) Si tool no disponible o falla:
   - degradar a respuesta normal de chat
4) Consumir contratos desde `/schemas` (no definir schemas paralelos en servicio).

Restricciones:
- No hacer llamadas reales a Google/Outlook.
- No romper ruta existente `/api/v2/chat`.

DoD:
- Pipeline compila y pasa tests.
- Tool path protegido por feature flag (`TOOLS_ENABLED`).
```

---

## Prompt IA-W2-03: Agenda Tool Placeholder (dominio)

```text
Actua como Domain Backend Engineer. Implementa el AgendaTool placeholder.

Objetivo:
- Preparar flujo negociacion de cita con contacto asignado sin integracion externa real.

Scope permitido:
- services/inference-stack-v2/inference-core-v2/app/services/
- services/inference-stack-v2/inference-core-v2/app/repositories/
- tests correspondientes

Tareas:
1) Crear AgendaTool con acciones stub:
   - detect_intent
   - get_assigned_contact
   - get_availability
   - propose_slots
   - confirm_slot
   - create_appointment_placeholder
2) Implementar state machine de negociacion (placeholder).
3) Resolver contacto asignado desde DB (tenant-scoped) con consultas seguras.
4) Persistir resultado placeholder de cita en estructura local (sin provider externo).

Restricciones:
- Sin acceso real a Google/Outlook.
- Sin hardcodes de tenant.

DoD:
- Tests de transiciones de estado.
- Tests de fallback cuando no hay contacto asignado.
```

---

## Prompt IA-W2-04: Calendar Providers Interface (Google/Outlook stubs)

```text
Actua como Integrations Engineer. Crea capa de proveedores de calendario desacoplada.

Objetivo:
- Definir interfaz comun para proveedores y adapters stub de Google/Outlook.

Scope permitido:
- services/inference-stack-v2/inference-core-v2/app/integrations/calendar/
- tests unitarios de adapters stub

Tareas:
1) Definir interfaz `CalendarProvider`:
   - get_availability(...)
   - create_event(...)
   - cancel_event(...)
2) Implementar:
   - GoogleCalendarProviderStub
   - OutlookCalendarProviderStub
3) Factory por provider (`google`, `outlook`) bajo feature flag.
4) Respuestas deterministicas de placeholder (no red).

Restricciones:
- No usar credenciales reales.
- No llamadas HTTP externas reales.

DoD:
- Adapters stubs testeados.
- Factory con manejo de provider no soportado.
```

---

## Prompt IA-W2-05: Persistencia y auditoria de tools (placeholders)

```text
Actua como Data/Backend Engineer. Prepara persistencia para tools y agenda.

Objetivo:
- Dejar tablas/campos de soporte para trazabilidad e idempotencia sin activar flujo productivo completo.

Scope permitido:
- migrations/
- services/inference-stack-v2/inference-core-v2/app/repositories/
- tests de repositorio

Tareas:
1) Crear migraciones para:
   - tool_executions (trace, status, payload resumido)
   - appointment_negotiations (estado por conversacion)
   - mapeo appointment <-> external_event_id/provider
2) Agregar repositorio SQL explicito para esas entidades.
3) Agregar idempotency_key en operaciones de booking placeholder.

Restricciones:
- No tocar tablas legacy sin justificacion.
- Mantener tenant scope obligatorio.

DoD:
- Migraciones aplicables.
- Repositorio con pruebas basicas CRUD.
```

---

## Prompt IA-W2-06: Bridge/Adapter output para agenda (UI placeholders)

```text
Actua como Backend UX Engineer (SDUI + canales).

Objetivo:
- Agregar componentes placeholders de agenda en salida sin romper policies por vertical/canal.

Scope permitido:
- services/web/realtor-chat/backend/app/transformer/
- services/web/realtor-chat/backend/app/adapters/
- schemas/chat_vertical_policy.v1.json
- tests integration del bridge

Tareas:
1) Definir componentes SDUI placeholder:
   - calendar_slot_picker
   - appointment_summary_card
   - appointment_confirm_actions
2) En `realtor`, permitir componentes de agenda segun policy.
3) En `generic`, mantener salida limitada (agenda simple / chat_text).
4) Para Meta/API, degradar a formatos soportados (texto/list/quick replies).
5) Extender `chat_vertical_policy.v1.json` con `enabled_tools` por vertical/canal.

Restricciones:
- No hardcodear policy fuera de `/schemas/chat_vertical_policy.v1.json`.
- No mover logica de negocio al frontend.

DoD:
- Tests por canal que validen degradacion y policy enforcement.
```

---

## Prompt IA-W2-07: QA tecnico y readiness de Wave 2

```text
Actua como QA/Release Engineer. Valida readiness de arquitectura Tooling Wave 2.

Objetivo:
- Confirmar que los placeholders quedaron integrados sin regresion del chat.

Scope permitido:
- tests integration/smoke
- dashboards/logging/flags
- docs tecnicos de validacion

Tareas:
1) Matriz de pruebas:
   - web_html realtor/generic
   - meta_whatsapp/meta_ig
   - api
2) Verificar:
   - tool flags ON/OFF
   - fallback correcto cuando provider es stub
   - aislamiento tenant
3) Validar logs:
   - tool_trace_id
   - tool_status
   - latencias de tool
4) Entregar reporte GO/NO-GO de Wave 2.

Restricciones:
- No introducir cambios funcionales nuevos fuera de test/instrumentacion.

DoD:
- Reporte reproducible con evidencias archivo:linea y resultados de pruebas.
```

---

## Orden recomendado (Wave 2)
1. IA-W2-01 (contratos en `/schemas`)
2. IA-W2-02 (framework tools)
3. IA-W2-03 + IA-W2-04 (agenda + providers stubs en paralelo)
4. IA-W2-05 (persistencia)
5. IA-W2-06 (outputs/adapters)
6. IA-W2-07 (QA readiness)

## Criterios de cierre Wave 2
1. Contratos unicos en `/schemas`.
2. Tooling funcional en modo placeholder bajo flags.
3. Sin regresion del chat actual.
4. Policies por vertical/canal respetadas.
5. Evidencia de pruebas en contenedor correcto.


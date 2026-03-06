# Prompts Especificos Para Asignar a Diferentes IAs

## Objetivo
Este documento contiene prompts listos para usar con diferentes IAs para implementar la arquitectura de chat multi-canal con ruteo por vertical (`realtor` vs `generic`), memoria corta compartida y adapters de salida por canal.

## Fuente Canonica de Politicas (obligatoria)
- Archivo unico de politicas por vertical/canal:
  - `/srv/datasyncsa/schemas/chat_vertical_policy.v1.json`
- Nombre de contrato: `ChatVerticalPolicyV1`
- Regla:
  - Ninguna IA debe crear copias de esta configuracion en `services/...`.
  - Todas las estrategias/adapters deben consumir esta fuente.

## Convenciones de Asignacion
- Cada prompt esta pensado para una IA distinta.
- Cada IA debe tocar solo los archivos en su scope.
- Si una IA detecta necesidad fuera de scope, debe documentarlo en `PENDING_HANDOFF.md` sin editar fuera de su area.
- No ejecutar `pytest` en host. Validar con contenedores segun `.agent/PY_EXECUTION_MAP.md`.

## Nomenclatura de Identidad (obligatoria)
- `channel_user_id`: identificador conversacional del canal (web/meta/api).
- `auth_user_id`: identificador de autenticacion interna (JWT/backoffice), opcional para trazabilidad.
- Regla: no usar `user_id` ambiguo en contratos nuevos.

## Ejemplos JSON Canonicos (obligatorios)

Request canonico minimo:

```json
{
  "client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
  "channel": "web_html",
  "channel_user_id": "web_2f8c7ed5-8e75-4d86-8d7d-5be326a5e2be",
  "message_text": "Hola"
}
```

Request canonico completo:

```json
{
  "client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
  "channel": "meta_whatsapp",
  "channel_user_id": "wa_50688887777",
  "auth_user_id": "admin_123",
  "conversation_id": "9f579ceb-5f9e-45f7-8408-906f6a36e326",
  "message_text": "Quiero ver casas en Escazu",
  "brand_project": "default",
  "metadata": {
    "utm_source": "meta",
    "locale": "es-CR"
  }
}
```

Response canonico interno:

```json
{
  "conversation_id": "9f579ceb-5f9e-45f7-8408-906f6a36e326",
  "canonical_answer": "Claro, te comparto opciones disponibles.",
  "intent": "property_search",
  "payload": {
    "components": [
      {
        "type": "chat_text",
        "text": "Claro, te comparto opciones disponibles."
      }
    ]
  },
  "meta": {
    "vertical": "realtor",
    "channel": "meta_whatsapp"
  }
}
```

---

## Prompt IA-01: Arquitectura de Contrato Canonico

```text
Actua como Senior Backend Engineer. Implementa solo la capa de contratos canonicos de chat para unificar canales (web_html, meta_whatsapp, meta_ig, api).

Objetivo:
- Crear modelos Pydantic de entrada/salida internos para el gateway.
- No implementar logica de negocio ni llamadas externas.

Scope permitido:
- services/web/realtor-chat/backend/app/schemas/
- services/web/realtor-chat/backend/app/core/
- tests unitarios asociados a esos schemas
- schemas/chat_vertical_policy.v1.json (solo para definir contrato base y estructura inicial)

Tareas:
1) Crear InternalChatRequest con campos:
   - client_id (UUID)
   - channel (Literal: web_html, meta_whatsapp, meta_ig, api)
   - channel_user_id (str)
   - auth_user_id (str opcional)
   - message_text (str)
   - conversation_id (UUID opcional)
   - metadata (dict)
   - brand_project (opcional)
2) Crear InternalChatResponse con:
   - conversation_id (UUID)
   - canonical_answer (str)
   - intent (opcional)
   - payload (dict)
   - debug/meta opcional
3) Crear validadores robustos (aliases snake/camel).
4) Agregar tests unitarios de parseo y validacion.

Restricciones:
- No tocar main.py ni routers.
- No tocar inference ni session manager.
- No crear archivos alternos de policy fuera de `schemas/chat_vertical_policy.v1.json`.
- No usar `user_id` ambiguo en contratos nuevos.

Entrega esperada:
- Nuevos schemas + tests verdes en contenedor realtor-api.
- Resumen de decisiones de contrato en comentario final.
```

---

## Prompt IA-02: Session Service Compartido (Redis)

```text
Actua como Backend Engineer especializado en estado conversacional. Implementa memoria corta compartida por canal.

Objetivo:
- Estandarizar session key por (client_id, channel, channel_user_id).
- Mantener compatibilidad con session actual cuando sea posible.

Scope permitido:
- services/web/realtor-chat/backend/app/session/
- services/web/realtor-chat/backend/app/core/
- tests de session/integration de backend realtor

Tareas:
1) Crear helper de keying: session:{client_id}:{channel}:{channel_user_id}
2) Extender SessionManager con:
   - get_session(client_id, channel, channel_user_id)
   - upsert_session(...)
   - delete_session(...)
3) Soportar fallback temporal al esquema antiguo para no romper flujo actual.
4) Definir TTL configurable por env var.
5) Agregar tests de aislamiento por tenant+channel+channel_user.

Restricciones:
- No tocar transformers SDUI.
- No cambiar contratos del inference-core-v2.
- No usar `user_id` ambiguo en firmas nuevas.

Validacion:
- Ejecutar pruebas en contenedor realtor-api.
- Documentar variables nuevas en `.env.example` si aplica.
```

---

## Prompt IA-03: Vertical Router (realtor vs generic)

```text
Actua como Backend Engineer enfocado en multi-tenant routing.

Objetivo:
- Resolver vertical por client_id y enrutar estrategia de respuesta.

Scope permitido:
- services/web/realtor-chat/backend/app/core/
- services/web/realtor-chat/backend/app/modules/ (si aplica)
- tests unitarios/integration de routing
- lectura de `schemas/chat_vertical_policy.v1.json` para resolver capacidades por vertical/canal

Tareas:
1) Implementar VerticalResolver:
   - input: client_id
   - output: vertical_slug (realtor | generic)
   - fuente: DB tenant-scoped
2) Implementar VerticalRouter:
   - selecciona strategy handler en runtime
3) Agregar cache liviano opcional por client_id (TTL corto).
4) Manejar fallback seguro si vertical no configurado.

Restricciones:
- No tocar canales Meta/Web output aun.
- No hardcodear client_ids en codigo.
- No duplicar la configuracion de politicas en codigo.

DoD:
- Tests que verifiquen que dos client_id distintos enrutan a estrategias distintas.
- Error controlado cuando vertical no existe.
```

---

## Prompt IA-04: Estrategia Realtor (UI rica SDUI)

```text
Actua como AI UX Backend Engineer para SDUI.

Objetivo:
- Implementar policy de salida para vertical realtor con componentes ricos.

Scope permitido:
- services/web/realtor-chat/backend/app/transformer/
- services/web/realtor-chat/backend/app/schemas/ui*.py
- tests de transformer
- lectura de `schemas/chat_vertical_policy.v1.json` (sin redefinir componentes en otro archivo)

Tareas:
1) Crear RealtorRendererPolicy con whitelist:
   - property_card
   - gallery
   - map
   - calendar
   - chat_text
2) Implementar compositor deterministico:
   - usa datos de AI + datos de negocio cuando aplique
3) Si falta data para componente rico, degradar a chat_text.
4) Garantizar que payload final no incluya componentes fuera de whitelist.

Restricciones:
- No tocar generic policy.
- No mover logica de negocio al frontend.
- No hardcodear whitelist en multiples archivos; tomarla de la policy central.

DoD:
- Tests de snapshots SDUI para respuestas realtor.
- Casos de fallback validados.
```

---

## Prompt IA-05: Estrategia Generic (UI limitada)

```text
Actua como Backend Engineer para salida controlada por politica.

Objetivo:
- Implementar policy generic con salida simple.

Scope permitido:
- services/web/realtor-chat/backend/app/transformer/
- tests de transformer
- lectura de `schemas/chat_vertical_policy.v1.json` (sin redefinir componentes en otro archivo)

Tareas:
1) Crear GenericRendererPolicy con whitelist:
   - agenda
   - image
   - chat_text
2) Filtrar cualquier componente no permitido proveniente de capas previas.
3) Degradar a chat_text si no hay componentes permitidos.
4) Mantener consistencia de contrato SDUI.

Restricciones:
- No tocar realtor policy.
- No cambiar inference payload.
- No hardcodear whitelist en multiples archivos; tomarla de la policy central.

DoD:
- Tests donde input intente producir map/card y policy generic lo bloquee.
```

---

## Prompt IA-06: Adapter Web HTML

```text
Actua como Backend Integrations Engineer.

Objetivo:
- Asegurar que el canal web_html reciba SDUI completo estandarizado.

Scope permitido:
- services/web/realtor-chat/backend/app/main.py
- services/web/realtor-chat/backend/app/schemas/
- tests integration API

Tareas:
1) Normalizar request web a InternalChatRequest.
2) Conectar pipeline: session -> resolver vertical -> inference -> strategy -> response.
3) Responder siempre en contrato SDUI estable para frontend.
4) Preservar compatibilidad con /chat/init existente.

Restricciones:
- No implementar Meta aqui.

DoD:
- Tests integration de /chat y /chat/init en flujo realtor y generic.
```

---

## Prompt IA-07: Adapter Meta (WhatsApp/Instagram)

```text
Actua como Backend Engineer experto en canales externos.

Objetivo:
- Traducir respuesta canonica a formato Meta compatible.

Scope permitido:
- nuevo modulo sugerido: services/web/realtor-chat/backend/app/adapters/meta/
- router/endpoints internos de salida para meta
- tests del adapter

Tareas:
1) Crear MetaOutputAdapter con transformaciones:
   - chat_text -> text
   - agenda -> lista/quick replies segun limite
   - image -> media payload
2) Agregar reglas de degradacion cuando componente no sea soportado por Meta.
3) Generar payload final deterministicamente (sin HTML ni SDUI crudo).

Restricciones:
- No cambiar contratos internos canonicos.
- No romper adapter web.

DoD:
- Tests unitarios del mapper por tipo de componente.
- Fixtures de payloads validos para meta_whatsapp y meta_ig.
```

---

## Prompt IA-08: Adapter API Externa (Integradores)

```text
Actua como API Platform Engineer.

Objetivo:
- Exponer respuesta JSON estable para terceros (channel=api).

Scope permitido:
- services/web/realtor-chat/backend/app/api/
- services/web/realtor-chat/backend/app/schemas/
- tests contract/integration

Tareas:
1) Definir contrato versionado (ej: /api/external/v1/chat).
2) Mapear salida interna a JSON limpio, documentado y estable.
3) Incluir metadata minima util (conversation_id, vertical, status).
4) Implementar manejo de errores consistente (4xx/5xx).

Restricciones:
- No exponer detalles internos de scoring privados.
- No mezclar con contrato SDUI web.

DoD:
- Tests de contrato y ejemplos de request/response.
```

---

## Prompt IA-09: Prompting por Vertical + Canal

```text
Actua como Prompt Engineer para inference-core-v2.

Objetivo:
- Definir plantillas de prompt por vertical y restricciones de canal.

Scope permitido:
- services/inference-stack-v2/inference-core-v2/
- tablas/config de prompts versionados
- tests del orquestador de prompts

Tareas:
1) Definir estrategia de seleccion:
   - vertical (realtor/generic)
   - canal (web_html/meta/api)
2) Mantener separacion: prompt decide semantica, backend decide render final.
3) Agregar placeholders estructurados para mejorar extraccion de intent.
4) Documentar versionado de prompts y rollback.

Restricciones:
- No meter HTML/components en prompt como fuente de verdad de UI.

DoD:
- Evidencia de seleccion correcta de prompt por vertical+canal.
```

---

## Prompt IA-10: QA, Observabilidad y Rollout

```text
Actua como QA/DevOps Engineer.

Objetivo:
- Validar extremo a extremo y preparar despliegue gradual sin romper produccion.

Scope permitido:
- tests integration/smoke
- configuraciones de feature flags
- dashboards/logging estructurado

Tareas:
1) Crear matriz de pruebas por canal x vertical:
   - web_html: realtor/generic
   - meta_whatsapp: realtor/generic
   - meta_ig: realtor/generic
   - api: realtor/generic
2) Instrumentar logs con:
   - client_id, channel, vertical, conversation_id, latency_ms
3) Definir feature flags:
   - CHANNEL_GATEWAY_ENABLED
   - VERTICAL_ROUTING_ENABLED
   - META_ADAPTER_ENABLED
4) Plan canary por tenants y rollback rapido.

Restricciones:
- No introducir cambios funcionales en estrategia de negocio.

DoD:
- Reporte de pruebas + checklist de release + plan de rollback validado.
```

---

## Orden Recomendado de Ejecucion (Handoffs)
1. IA-01 (contratos) -> IA-02 (session) -> IA-03 (router)
2. IA-04 y IA-05 en paralelo (strategies)
3. IA-06 (web adapter)
4. IA-07 y IA-08 en paralelo (meta/api)
5. IA-09 (prompting) en paralelo desde que IA-03 este estable
6. IA-10 al final de cada fase para gate de calidad

## Checklist de Cierre por IA
- Scope respetado.
- Tests del modulo ejecutados en contenedor correcto.
- Variables nuevas documentadas en `.env.example`.
- Handoff escrito: cambios, riesgos, pendientes.

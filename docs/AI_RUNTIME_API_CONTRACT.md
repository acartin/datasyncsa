# AI Runtime API Contract

Contrato vigente del runtime conversacional `ai-runtime`.

La fuente ejecutable está en:

- [services/ai_runtime/domain/contracts.py](/srv/datasyncsa/services/ai_runtime/domain/contracts.py:296)
- [services/ai_runtime/api.py](/srv/datasyncsa/services/ai_runtime/api.py:124)
- [services/ai_runtime/runtime/service.py](/srv/datasyncsa/services/ai_runtime/runtime/service.py:100)

## Endpoint principal

`POST /api/v1/chat`

## Request canónico

El contrato interno y de salida usa `snake_case`.

```json
{
  "client_id": "tenant-id",
  "message": "string",
  "conversation_id": "uuid-opcional",
  "session_id": "uuid-opcional",
  "user_id": "uuid-opcional",
  "flow": "basic_flow|realtor_flow-opcional",
  "metadata": {}
}
```

Campos relevantes:

- `client_id` es obligatorio.
- `message` es obligatorio.
- `flow` puede omitirse; el runtime lo resuelve desde el vertical del tenant.
- `metadata` carga contexto de canal, tracking y continuidad.

## Aliases de entrada aceptados

Por compatibilidad, el parser acepta también:

- `clientId` -> `client_id`
- `queryText`, `query_text`, `text` -> `message`
- `sessionId` -> `session_id`
- `conversationId` -> `conversation_id`
- `userId` -> `user_id`
- `userMetadata` -> `metadata`

Estos aliases solo aplican a entrada. La respuesta del runtime sale en `snake_case`.

## Response canónico

```json
{
  "session_id": "uuid",
  "conversation_id": "uuid",
  "client_id": "tenant-id",
  "vertical": "realtor|healthcare|legal|insurance",
  "answer": "string",
  "components": [],
  "sources": [],
  "ui_payload": {},
  "render_mode": "cards|text|null",
  "cards_mode": "spotlight|gallery|null",
  "escalated": false,
  "scoring_status": "disabled",
  "metadata": {
    "flow": "basic_flow|realtor_flow",
    "turn": 1,
    "trace_id": "uuid"
  }
}
```

Notas:

- `render_mode` y `cards_mode` salen solo cuando el estado final los define.
- `components` y `ui_payload` son vacíos o `null` fuera de verticales que renderizan UI estructurada.
- `scoring_status` hoy sale como `"disabled"` desde el runtime principal.

## Endpoints auxiliares

### Health

`GET /api/v1/health`

```json
{
  "status": "ok",
  "service": "datasyncsa-ai-runtime"
}
```

### Internal memory reset

`POST /api/v1/internal/memory/reset`

Request:

```json
{
  "client_id": "tenant-id",
  "reason": "string-opcional"
}
```

Response:

```json
{
  "status": "ok",
  "client_id": "tenant-id",
  "conversations_deleted": 3,
  "cache_keys_deleted": 7
}
```

### Internal session reset

`POST /api/v1/internal/session/reset`

Request:

```json
{
  "client_id": "tenant-id",
  "session_id": "uuid",
  "reason": "string-opcional"
}
```

Response:

```json
{
  "status": "ok",
  "client_id": "tenant-id",
  "session_id": "uuid",
  "state_deleted": true,
  "lead_deleted": true,
  "trace_deleted": true
}
```

## Reglas de borde

1. Ninguna operación conversacional ocurre sin `client_id`.
2. El runtime es `multitenant-first`: estado, cache y RAG se resuelven por tenant.
3. `realtor_flow` solo aplica a `vertical = realtor`.
4. `basic_flow` aplica a verticales no realtor.
5. El canal web productivo suele consumir este contrato a través de `chat-web-renderer`, no desde el navegador directo.
6. El contrato externo no expone detalles internos del grafo ni IDs de referencia intermedios.

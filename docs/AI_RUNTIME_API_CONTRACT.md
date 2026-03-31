# AI Runtime API Contract

Contrato activo del runtime conversacional `ai-runtime`.

## Endpoint principal

`POST /api/v1/chat`

## Request canonico

```json
{
  "clientId": "tenant-id",
  "queryText": "string",
  "conversationId": "uuid-opcional",
  "sessionId": "uuid-opcional",
  "userId": "uuid-opcional",
  "flow": "basic_flow|realtor_flow-opcional",
  "userMetadata": {}
}
```

Campos relevantes:

- `clientId` es obligatorio
- `queryText` es obligatorio
- `flow` puede omitirse; el runtime lo resuelve por vertical cuando aplique
- `flow` selecciona el grafo interno y no implica servicios HTTP intermedios
- `userMetadata` se usa para contexto de canal, tracking y continuidad

## Response canonico

```json
{
  "sessionId": "uuid",
  "conversationId": "uuid",
  "clientId": "tenant-id",
  "vertical": "realtor|healthcare|legal|insurance",
  "answer": "string",
  "components": [],
  "sources": [],
  "uiPayload": {},
  "renderMode": "cards|text|null",
  "cardsMode": "spotlight|gallery|null",
  "escalated": false,
  "scoringStatus": "disabled",
  "metadata": {
    "flow": "basic_flow|realtor_flow",
    "turn": 1
  }
}
```

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
  "clientId": "tenant-id",
  "reason": "string-opcional"
}
```

Response:

```json
{
  "status": "ok",
  "clientId": "tenant-id",
  "conversationsDeleted": 3,
  "cacheKeysDeleted": 7
}
```

## Reglas de borde

1. Ninguna operacion conversacional ocurre sin `client_id`.
2. El runtime es multitenant-first: estado, cache y RAG se resuelven por tenant.
3. `realtor_flow` solo debe usarse con vertical `realtor`.
4. `basic_flow` solo debe usarse con verticales no realtor.
5. Los bridges HTTP legacy fueron retirados del compose activo; el cliente recomendado llama directo a `ai-runtime`.
6. El contrato externo no expone detalles internos del grafo ni IDs de referencia intermedios.

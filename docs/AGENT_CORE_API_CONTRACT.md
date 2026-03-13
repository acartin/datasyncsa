# Agent Core API Contract (Target)

## Endpoint principal

`POST /api/v1/chat`

## Request

```json
{
  "clientId": "uuid",
  "conversationId": "uuid-opcional",
  "queryText": "string",
  "channel": "web_html|meta_whatsapp|meta_ig|api",
  "filters": {},
  "userMetadata": {}
}
```

## Response

```json
{
  "answer": "string",
  "conversationId": "uuid",
  "leadId": "uuid-opcional",
  "intent": "string-opcional",
  "routeMode": "answer_only|tool_required|clarify|reject",
  "activeSubflow": "string",
  "components": [],
  "metadata": {},
  "scoringStatus": "disabled|pending|error",
  "scoringJobId": "uuid-opcional",
  "scoringEta": "iso-opcional"
}
```

## Endpoint de salud

`GET /health`

```json
{
  "status": "ok",
  "service": "agent-core"
}
```

## Reglas

1. `components` se deriva de `ToolResult` y renderer determinista.
2. En `clarify`, no se ejecutan tools.
3. En `reject`, el motivo va en metadata técnica.
4. No exponer internals del grafo al cliente final.

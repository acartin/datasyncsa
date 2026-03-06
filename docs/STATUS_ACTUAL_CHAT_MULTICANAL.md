# STATUS ACTUAL: CHAT MULTICANAL

- Fecha de corte (UTC): `2026-03-05`
- Estado general: `ACTIVO Y VALIDADO`

## 1) Contrato canónico vigente

- Endpoint activo: `POST /chat`
- Contrato de entrada: `InternalChatRequest`
- Restricción actual: solo `channel=web_html` (`422` para no-web)
- Endpoint retirado: `POST /chat/v2` (eliminado)
- API externa v1: no expuesta en runtime (`/api/external/v1/chat` retorna `404`)

## 2) Resolución de flujo (Generic vs Realtor)

El flujo no se decide por URL, se decide por `client_id`:

1. `client_id` -> `lead_clients.vertical_id`
2. `vertical_id` -> `lead_client_verticals.slug`
3. Normalización backend:
   - `real-estate`, `real_estate`, `inmobiliaria`, `realtor` -> `realtor`
   - `generic` -> `generic`
   - cualquier otro slug -> `generic` (fallback)

Resultado:
- Clientes `real-estate` ya enrutan al flujo `realtor` correctamente.

## 3) Feature flags vigentes

- `SESSION_MULTICHANNEL_ENABLED`:
  - `false`: sesión por `client_id`
  - `true`: sesión por `(client_id, channel, channel_user_id)`

Flags retiradas del flujo canónico:
- `INTERNAL_CHAT_V2_ENABLED`
- `EXTERNAL_API_V1_ENABLED`

## 4) Validación reciente

- `realtor-api`:
  - tests runtime/integration relevantes en verde
- `inference-core-v2`:
  - rebuild de `inference-core-v2` + `inference-core-v2-worker` ejecutado
  - tests de `prompt_selector/scoring_orchestrator` en verde

## 5) Archivos clave

- `services/web/realtor-chat/backend/app/main.py`
- `services/web/realtor-chat/backend/app/core/vertical_router.py`
- `services/inference-stack-v2/inference-core-v2/app/services/prompt_selector.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py`
- `services/web/realtor-chat/backend/tests/unit/test_chat_runtime.py`

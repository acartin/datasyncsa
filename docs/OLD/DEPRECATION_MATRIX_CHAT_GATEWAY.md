# Deprecation Matrix - Chat Gateway

## Estado actual (2026-03-05)

Arquitectura canónica:
- `POST /chat` como único endpoint interno web activo.
- Ruteo por vertical normalizada (`realtor`/`generic`) según `client_id`.

## Matriz

| Componente | Estado |
|---|---|
| `POST /chat` (`InternalChatRequest`) | **Activo canónico** |
| `POST /chat/v2` | **Retirado** |
| `POST /api/external/v1/chat` | **Retirado/no expuesto** |
| `INTERNAL_CHAT_V2_ENABLED` | **Retirado** |
| `EXTERNAL_API_V1_ENABLED` | **Retirado** |
| `SESSION_MULTICHANNEL_ENABLED` | **Activo** |

## Regla de vertical operativa

- `real-estate`, `real_estate`, `inmobiliaria`, `realtor` -> `realtor`
- `generic` -> `generic`
- otros slugs -> `generic` (fallback)

## Nota

Si se reabre API externa en el futuro, debe hacerse como contrato nuevo y no reactivar `v1` legacy.

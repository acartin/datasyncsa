# CHANGE_LOG_CHAT

## 2026-02-20 - Migración a Inference Core V2

### Resumen

Se migró el servicio `realtor-chat` para utilizar `inference-core-v2` y `generic-bridge-v2` en lugar de `inference-core` (v1).

### Cambios Realizados

#### 1. `services/web/realtor-chat/backend/app/core/inference_bridge.py`

- Se agregó soporte multi-version: `INFERENCE_VERSION` configurable (`v1` o `v2`)
- Por defecto ahora usa `v2`
- Se implementó el método `_chat_v2()` que llama a `/api/v2/chat`
- Se agregó `_normalize_v2_response()` para convertir la respuesta de v2 al formato esperado por el transformer
- Se mantiene backward compatibility con v1 mediante el método `_chat_v1()`

##### Variables de entorno:
- `INFERENCE_VERSION`: `v2` (default) o `v1`
- `INFERENCE_V2_URL`: URL de inference-core-v2 (default: `http://inference-core-v2:8000/api/v2`)
- `INFERENCE_CORE_URL`: URL de inference-core-v1 (legacy)

#### 2. `services/web/realtor-chat/backend/app/core/memory_reset.py`

- Se agregó soporte para configuración de versión
- Por defecto intenta usar v2, pero como v2 no tiene endpoint de memory reset, cae back a v1
- Nueva variable `INFERENCE_V2_RESET_URL` para configuración opcional

##### Variables de entorno:
- `INFERENCE_VERSION`: `v2` (default) o `v1`
- `INFERENCE_V2_RESET_URL`: (opcional) URL del endpoint de reset en v2
- `INFERENCE_CORE_RESET_URL`: URL del endpoint de reset en v1 (fallback)

#### 3. `docker-compose.yml`

- Se agregaron las nuevas variables de entorno al servicio `realtor-api`:
  - `INFERENCE_VERSION=v2`
  - `INFERENCE_V2_URL=http://inference-core-v2:8000`
- Se agregó `inference-core-v2` a `depends_on` del servicio `realtor-api`

#### 4. `services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py`

- Se agregó método `_generate_chat_response()` que:
  - Obtiene el system prompt desde `lead_ai_prompts` (cliente o global)
  - Usa el LLM (Gemini) para generar respuesta
- Se modificó `process_chat()` para usar respuesta real en lugar de placeholder
- Scoring sigue ejecutándose en background

#### 5. `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`

- Se agregó método `get_client_system_prompt()` para obtener el prompt de chat desde `lead_ai_prompts`

#### 6. Base de datos

- Se agregó scoring prompt para el modelo de scoring:
  ```sql
  INSERT INTO lead_scoring_prompts (model_id, version, prompt_template, ...) 
  VALUES ('53fe9e76-09e6-46af-a934-bc2c602c256b', 1, '...', true);
  ```

- Se agregó system prompt para el cliente:
  ```sql
  INSERT INTO lead_ai_prompts (client_id, slug, prompt_text, is_active)
  VALUES ('64f357a0-98eb-44f1-9f41-6e615ed26180', 'primary_chat', '...', true);
  ```

### Arquitectura

```
realtor-chat (Frontend)
    │
    ▼
realtor-api (Bridge)
    │
    └── INFERENCE_VERSION=v2 ──► inference-core-v2 (v2)
                                    │
                                    ├── 1. Obtiene system prompt desde lead_ai_prompts
                                    ├── 2. Genera respuesta con LLM (Gemini)
                                    └── 3. Scoring en background (lead_scoring_prompts)
```

### Rollback

Para volver a usar v1:

```bash
# En docker-compose.yml o .env
INFERENCE_VERSION=v1
```

### Testing

```bash
# Probar chat directamente
curl -X POST http://localhost:8091/api/v2/chat \
  -H "Content-Type: application/json" \
  -d '{"queryText": "Hola", "clientId": "64f357a0-98eb-44f1-9f41-6e615ed26180"}'
```

### Notas

- El scoring v2 requiere que el tenant tenga configurada una vertical con modelo de scoring activo
- El endpoint de memory reset sigue apuntando a v1 ya que v2 no implementa esta funcionalidad
- La respuesta de v2 incluye datos de scoring (`scorecard`) que son normalizados para el transformer
- El system prompt del chat se configura en `lead_ai_prompts` (slug: `primary_chat`)

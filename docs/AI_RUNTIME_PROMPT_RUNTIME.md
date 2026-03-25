# AI Runtime Prompt Runtime

## Objetivo

Definir como `ai-runtime` compone prompts en runtime sin hardcodear negocio en codigo.

## Capas de prompt

1. Capa tenant
- `tone_prompt`
- editable por tenant
- define tono, nombre del bot y estilo

2. Capa vertical
- prompts base por vertical y por nodo
- definen planeacion, sintesis y comportamiento compartido

3. Capa contexto
- estado actual
- referencias resueltas
- outputs del turno
- chunks RAG y entidades relevantes

## Composicion

`prompt_final = tone_prompt + vertical_prompt + context`

Implementacion activa:

- `services/ai_runtime/config/prompt_composer.py`

## Ubicacion de prompts

- base compartidos:
  - `services/ai_runtime/graph/_shared/prompts/*.py`
- por vertical:
  - `services/ai_runtime/graph/_shared/prompts/vertical/realtor/`
  - `services/ai_runtime/graph/_shared/prompts/vertical/healthcare/`
  - `services/ai_runtime/graph/_shared/prompts/vertical/legal/`
- realtor especificos:
  - `services/ai_runtime/graph/realtor/prompts/*.py`

## Reglas operativas

1. El tenant no redefine contratos estructurados del runtime.
2. El prompt no reemplaza reglas deterministas de estado, cola o render.
3. IDs, dependencias y mutaciones de estado se resuelven en codigo.
4. Los prompts JSON deben mantener schema estricto y sin markdown.
5. La composicion debe operar siempre con `tenant_config` y nunca con defaults hardcodeados de negocio.

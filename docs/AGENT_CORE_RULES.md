# Agent Core Rules

Reglas no negociables para `agent-core` y `scoring-core`.

## 1. Separacion de poderes

- Solo el planner de `agent-core` decide el turno.
- `scoring-core` no participa en la respuesta conversacional del turno.

## 2. Planner

- El planner decide exactamente una vez por turno.
- El planner produce salida estructurada y tipada.
- El planner nunca ve `ToolResult` del turno actual.
- El planner nunca escribe SQL libre.
- El planner puede devolver `clarify` como resultado legitimo del turno.

## 3. Gate y guardrail

- `policy gate` solo devuelve `accept` o `reject` con `reason_code`.
- `policy gate` nunca corrige, reescribe ni redirige el plan.
- `answer guardrail` solo devuelve `accept` o `reject` con `reason_code`.
- `answer guardrail` nunca reescribe la respuesta.

## 4. Tools

- Toda tool tiene contrato tipado de entrada y salida.
- SQL se genera solo desde slots tipados -> AST -> SQL.
- El LLM nunca emite `WHERE`, `JOIN`, `ORDER BY` ni SQL libre.
- `workflow` siempre es tipado e idempotente cuando aplique.

## 5. Cards

- Las cards no salen del synthesizer.
- Las cards se renderizan de manera determinista desde `ToolResult`.
- Si una card requiere reglas de negocio, esas reglas viven en renderer/config, no en prompts.

## 6. Verticales

- `generic` y `realtor` son verticales del mismo `agent-core`.
- No existen dos arquitecturas paralelas.
- Las diferencias entre verticales viven en prompts, policies, tool registry, contratos de slots y card registry.

## 7. Prompts

- Los prompts del sistema viven en `ai_system_prompts`.
- Los prompts/overrides por tenant viven en `lead_ai_prompts`.
- Los prompts de scoring viven en `lead_scoring_prompts`.
- Ninguna policy finita debe esconderse dentro de un prompt.

## 8. Scoring

- Scoring es un subsistema separado.
- `agent-core` no resuelve modelo ni prompt de scoring.
- `agent-core` no ejecuta scoring.
- `agent-core` solo dispara el side effect de scoring con identidad minima del caso.

## 9. Compatibilidad

- No se requiere compatibilidad interna con `inference-core-v1` o `inference-core-v2`.
- La compatibilidad relevante es la de contratos consumidos por otros modulos del monorepo.
- Si un contrato externo cambia, debe cambiarse coordinadamente en el mismo monorepo.

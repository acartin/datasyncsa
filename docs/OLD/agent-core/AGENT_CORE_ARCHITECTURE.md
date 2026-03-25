# Agent Core Architecture (Target)

## Resumen

`agent-core` será un servicio de conversación `LangGraph-first`.

Separa estrictamente:
- decisión conversacional (planner LLM)
- ejecución determinista (gate, tools, SQL translator, card renderer)
- redacción final (synthesizer LLM)

## Componentes

1. Input Normalizer
- Normaliza `tenant`, `channel`, `conversation_id`, `metadata`.
- Construye contexto operativo mínimo.

2. Planner LLM
- Entrada: historial + contexto + prompt de planner.
- Salida: `RouterDecision` tipado.
- No ejecuta herramientas.

3. Policy Gate
- Valida esquema, permisos tenant, tools permitidas, budget y confidence.
- Respuesta binaria `accept/reject`.

4. Tool Runtime
- Ejecuta tools permitidas en paralelo cuando aplique.
- Submódulos:
- `RAG` retriever
- `SQL translator` determinista
- `workflow executor` para side effects tipados

5. Card Renderer
- Convierte `ToolResult` a `CardModel`.
- No usa LLM.

6. Synthesizer LLM
- Entrada: `SynthesizerInput` (contexto resumido + tool results).
- Salida: `SynthesizerOutput`.
- No ve `RouterDecision`.

7. Answer Guardrail
- Verifica claims, evidencia y schema de salida.
- Respuesta binaria `accept/reject`.

8. Persistence
- Persiste envelope, decisión, tool results y trazas.
- Emite evento o enqueue hacia scoring (sin lógica de scoring local).

## Frontera con scoring

- `agent-core` solo invoca API de scoring para encolado y consulta de estado.
- No contiene motor, repositorios ni worker de scoring en su dominio.

## Modelo de errores

1. `goal=clarify`: respuesta de negocio válida.
2. `gate reject`: rechazo de seguridad/política.
3. `guardrail reject`: salida no confiable.
4. `tool failure`: degradación controlada según contrato.

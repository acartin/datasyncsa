# Agent Core Architecture

## Resumen

`agent-core` es el runtime conversacional soberano del sistema.

Tiene una sola arquitectura y multiples verticales.

- Un solo planner.
- Un solo runtime determinista.
- Un solo synthesizer.
- Verticales configurables: `generic`, `realtor`.

## Servicios

- `agent-core`
  - logica conversacional.
- `scoring-core`
  - scoring asincrono.

## Flujo del turno

1. Un canal o adaptador interno normaliza el request.
2. `agent-core` valida identidad tecnica del request.
3. `agent-core` resuelve tenant, vertical y prompt runtime.
4. El planner genera `RouterDecision`.
5. El `policy gate` acepta o rechaza.
6. Si el planner devolvio `clarify`, `agent-core` responde y termina.
7. Si la decision fue aceptada y requiere tools, el runtime ejecuta tools.
8. `card_renderer` genera cards desde `ToolResult`.
9. El synthesizer redacta el texto final.
10. El `answer guardrail` acepta o rechaza.
11. `agent-core` persiste exactamente el `AnswerEnvelope`.
12. `agent-core` dispara side effects asincronos, incluido scoring.

## Clarify vs Reject

`clarify` y `reject` no son equivalentes.

- `clarify`
  - resultado conversacional normal.
  - sale del planner.
  - produce una respuesta visible al usuario.

- `reject`
  - problema interno o violacion de policy.
  - sale del gate o del guardrail.
  - produce fallback seguro, no una aclaracion natural.

## Estado conversacional

`agent-core` debe leer estado estructurado, no blobs libres.

Componentes minimos del estado:

- `tenant`
- `vertical`
- `channel`
- `conversation_id`
- `history_window`
- `conversation_state`
- `last_cards`
- `last_tool_facts`

El planner lee estado estructurado.
El synthesizer lee estado estructurado y `ToolResult`.

## Verticales

`generic`:

- respuesta directa
- retrieval documental
- workflows simples cuando aplique
- sin cards complejas por defecto

`realtor`:

- busqueda y refinamiento
- slots inmobiliarios
- SQL determinista
- cards de propiedad y resumen de busqueda

La arquitectura no cambia por vertical.
Solo cambian configuracion, tools y contratos.

## Lo que `agent-core` no hace

- no calcula scoring
- no mantiene compatibilidad legacy por si misma
- no escribe SQL libre
- no renderiza componentes fuera del contrato
- no es repositorio de prompts de scoring

## Resultado final

El resultado visible del servicio es `AnswerEnvelope`:

- `text`
- `cards`
- `evidence_ids`
- `goal`
- `confidence`
- metadatos tecnicos minimos

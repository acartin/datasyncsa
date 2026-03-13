# Agent Core Implementation Plan

## Fase 0 - Congelación de arquitectura

1. Establecer invariantes y contratos tipados.
2. Definir nodos y edges de LangGraph.
3. Congelar frontera con scoring (solo API).

## Fase 1 - Runtime mínimo de LangGraph

1. Implementar `state`, `nodes`, `workflow`.
2. Conectar endpoint `/api/v1/chat` al grafo.
3. Soportar rutas `answer`, `clarify`, `reject`.

## Fase 2 - Tools deterministas

1. Integrar `RAG` tool.
2. Integrar `SQL translator` tipado.
3. Integrar `workflow executor` tipado.
4. Integrar `card_renderer` determinista.

## Fase 3 - Prompt runtime completo

1. Resolver prompts por tenant/canal.
2. Trazar versiones de prompt por turno.
3. Añadir observabilidad por nodo.

## Fase 4 - Guardrails y políticas

1. Activar gate binario por tenant.
2. Activar guardrail binario de evidencia.
3. Definir códigos de rechazo estables.

## Fase 5 - Persistencia y telemetría

1. Persistir `decision`, `tool_results`, `envelope`.
2. Exponer métricas por nodo y latencia total.

## Fase 6 - Sustitución del camino principal

1. Apuntar consumidores internos al `agent-core`.
2. Retirar dependencia funcional de inference legacy para chat.

## Nota de alcance

En esta fase no se refactoriza internamente `scoring`.

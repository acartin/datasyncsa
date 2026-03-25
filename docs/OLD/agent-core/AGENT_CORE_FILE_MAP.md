# Agent Core File Map (Target)

## Servicio

`services/agent-core/`

## Estructura objetivo

- `main.py`
- `app/api/chat.py`
- `app/core/config.py`
- `app/core/dependencies.py`
- `app/graph/state.py`
- `app/graph/nodes.py`
- `app/graph/workflow.py`
- `app/models/contracts.py`
- `app/runtime/policy_gate.py`
- `app/runtime/answer_guardrail.py`
- `app/runtime/persistence.py`
- `app/tools/executor.py`
- `app/tools/sql_translator.py`
- `app/tools/rag_client.py`
- `app/tools/workflow_executor.py`
- `app/renderers/card_renderer.py`
- `app/services/planner_service.py`
- `app/services/synthesizer_service.py`
- `app/services/scoring_client.py`

## Schemas compartidos

- `schemas/agent_core/contracts/`
- `schemas/agent_core/runtime/`

## Regla de ownership

- Conversación y decisión: `agent-core`.
- Scoring asíncrono: `scoring-core`.

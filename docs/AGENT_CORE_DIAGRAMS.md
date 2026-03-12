# Agent Core Diagrams

Documentacion visual del diseno propuesto para `agent-core`.

## Flujo End-to-End

![Agent Core End-to-End](./AGENT_CORE_FLOW.svg)

## Separacion Por Zonas

![Agent Core Zones](./AGENT_CORE_ZONES.svg)

## Nota

- `clarify` debe salir del planner como `goal`, no como efecto de `reject`.
- `gate` y `guardrail` solo aceptan o rechazan; no corrigen ni reescriben.
- `cards` se renderizan de forma determinista desde `ToolResult`.

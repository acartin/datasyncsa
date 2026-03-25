# AI Runtime Graph Diagrams

Archivos generados desde los builders reales de LangGraph del servicio `ai-runtime`.

- `generic-graph.mmd`
- `generic-graph.svg`
- `realtor-graph.mmd`
- `realtor-graph.svg`

## Regeneracion

Desde la raiz del repo:

```bash
.venv-langgraph/bin/python services/ai_runtime/scripts/export_graph_diagrams.py
```

Alternativamente, dentro del contenedor:

```bash
docker compose exec -T ai-runtime python /app/services/ai_runtime/scripts/export_graph_diagrams.py
```

## Notas

- el exportador usa la metadata del `builder` compilado (`edges` y `branches`)
- no ejecuta nodos ni necesita DB/Redis
- el SVG se genera localmente y no depende de servicios externos

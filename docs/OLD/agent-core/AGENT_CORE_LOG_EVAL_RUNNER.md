# Agent Core Log Eval Runner

## Objetivo

Definir cómo usar el runner de evaluación basado en logs para medir estabilidad de prompts/routing antes de producción.

Archivo ejecutable:
- `services/agent-core/app/evals/log_eval_runner.py`

## Estándar de nomenclatura

Este documento sigue la convención vigente de `docs`:
- Prefijo por dominio: `AGENT_CORE_`
- Nombre en mayúsculas con `_`
- Extensión `.md`

Por eso el nombre es:
- `docs/AGENT_CORE_LOG_EVAL_RUNNER.md`

## Qué evalúa

El runner consume eventos `llm_exchange` y `turn_complete` en `*.jsonl`, construye casos y evalúa:

1. Planner
- validez de contrato `RouterDecision`
- coherencia de `clarify`
- alineación `realtor_sql -> response_mode=text_plus_cards`
- chequeos de routing frecuentes (meta->rag, referenciales)

2. Synthesizer
- validez de contrato
- alineación `response_mode` vs `needs_cards`
- reglas de cards (2 frases cuando aplica, sin pedir permiso para mostrar)
- evidencia (`evidence_ids` válidos y no vacíos en RAG cuando aplica)
- continuidad RAG (evitar frase de reinicio)

3. Guardrail
- ejecución de `answer_guardrail`
- conteo de rechazos

## Modos de uso

1. Modo `logged-only` (sin llamadas LLM)
- Reusa outputs ya registrados en log.
- Útil para baseline rápido y auditoría.

2. Modo replay (default)
- Re-ejecuta planner/synthesizer con prompts/versiones actuales.
- Útil para medir regresión/mejora antes de release.

## Comandos

Ejecutar siempre en contenedor `agent-core`:

```bash
docker compose exec -T agent-core \
python -m app.evals.log_eval_runner \
--log-dir /app/log \
--logged-only \
--output /app/log/eval_logged.json
```

```bash
docker compose exec -T agent-core \
python -m app.evals.log_eval_runner \
--log-dir /app/log \
--output /app/log/eval_replay.json
```

Filtrar una conversación:

```bash
docker compose exec -T agent-core \
python -m app.evals.log_eval_runner \
--log-dir /app/log \
--conversation-id <conversation_id> \
--output /app/log/eval_one_conv.json
```

## Output y lectura

1. Resumen en consola
- casos planner/synth procesados
- errores de ejecución
- rechazos de guardrail
- pass/fail por regla

2. Reporte JSON (`--output`)
- `summary`: totales globales
- `rule_stats`: cumplimiento por regla
- `failed_rules`: lista accionable con `conversation_id`, `case_id` y detalle

## Flujo recomendado pre-release

1. Correr `--logged-only` para línea base.
2. Aplicar cambios de prompts/runtime.
3. Correr replay sobre el mismo set de logs.
4. Comparar `rule_stats` y `guardrail_rejects`.
5. Si baja pass-rate o suben rechazos, no promover a producción.

## Utilidad práctica para el equipo

1. Sustituye revisión manual de logs por métricas repetibles.
2. Detecta rápido regresiones en reglas sensibles.
3. Permite validar versiones de prompt con evidencia objetiva.
4. Deja trazabilidad de decisión de release con artefacto JSON.


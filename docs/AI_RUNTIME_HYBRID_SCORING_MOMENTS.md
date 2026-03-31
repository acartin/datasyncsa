# AI Runtime Hybrid Scoring + Moment Rules

## Objetivo

Documentar el refactor que combina:

- reglas rigidas de "mapa de momentos" por vertical para controlar la conversacion
- evaluacion LLM en memoria por turno para calificar y justificar cada pilar
- cero persistencia realtime en esta etapa (persistencia diferida para fase siguiente)

## Principio arquitectural

Separacion de responsabilidades:

1. Reglas rigidas: deciden **cuando preguntar** cada campo.
2. LLM scoring: decide **como puntuar** y **como justificar** cada criterio activo.
3. Estado del grafo: mantiene resultados fusionados por turno en `lead_advisor`.

## Flujo operativo por turno

1. Se carga `scoring_profile` del tenant desde BD (modelo + criterios + prompt + extraction schema).
2. `lead_advisor` ejecuta evaluacion LLM in-memory (`score_turn`) con prompt del modelo activo.
3. Se normalizan:
   - `criteria_scores`
   - `criteria_reasons`
   - `scoring_reasoning`
   - `scoring_confidence`
   - `lead_extracted` (mapeo `extracted_*` -> campos canonicos)
4. Se aplican reglas de momentos por vertical para elegir `field_to_ask`.
5. `synthesize` agrega la pregunta solo si corresponde.
6. No se persiste scorecard en `scoring-core` en este paso.

## Ubicacion de codigo

- Estado y normalizacion de scoring:
  - `services/ai_runtime/domain/state.py`
- Carga del modelo/prompt/scoring schema desde BD:
  - `services/data/repositories/tenant_repository.py`
- Evaluacion hibrida en memoria (prompt + parse + fallback):
  - `services/ai_runtime/graph/_shared/scoring_hybrid.py`
- Nodo principal de orquestacion de lead scoring + pregunta:
  - `services/ai_runtime/graph/_shared/nodes/lead_advisor_node.py`
- Reglas por vertical:
  - `services/ai_runtime/graph/realtor/moment_rules.py`
  - `services/ai_runtime/graph/generic/moment_rules.py`
- Trazabilidad de scoring en turn trace:
  - `services/ai_runtime/runtime/turn_trace.py`

## Reglas por vertical

### Realtor

Reglas duras orientadas a:

- nombre: despues de primer momento de calidez
- presupuesto: luego de reaccion a propiedad/precio
- aprobacion: al detectar intencion financiera
- fecha_preferida: con urgencia alta
- telefono/email: cerca de cierre
- tipo_cita: solo con match/intencion altos y sin `appointment_intent = negative`

### Generic (healthcare, legal, insurance)

Reglas mas simples, con la misma estructura:

- progresion de nombre -> intencion de cita -> contacto
- soporte de presupuesto/aprobacion/fecha/tipo_cita cuando apliquen
- fallback determinista al siguiente campo pendiente

## Contrato de salida de scoring LLM en memoria

Se acepta payload estilo:

- `scores` por criterio activo
- `score_reasons` por criterio (opcional, recomendado)
- `reasoning` global (opcional)
- `confidence` 0..1 (opcional)
- `extracted_data` (o `fields` legacy)

Si faltan scores:

- se aplica fallback conservador por criterio
- prioridad a politica en `scoring_contract` del modelo
- fallback final: rango bajo (default 1.5 dentro de limites min/max)

## Nota sobre persistencia

En esta fase:

- no se usa `scoring-core-worker` para persistir por turno
- no se upsertean `lead_scorecards/lead_score_items` desde `ai-runtime`
- todo vive en estado conversacional de sesion

Fase siguiente sugerida:

- persistir scorecard final al cierre de conversacion o hito de negocio.


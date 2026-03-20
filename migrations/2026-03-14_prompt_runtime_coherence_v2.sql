BEGIN;

-- lead_ai_prompts has unique (client_id, slug), so runtime version history is stored in this companion table.
CREATE TABLE IF NOT EXISTS public.lead_ai_prompt_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  prompt_id UUID NOT NULL REFERENCES public.lead_ai_prompts(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  prompt_text TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'migration',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (prompt_id, version)
);

CREATE INDEX IF NOT EXISTS lead_ai_prompt_versions_prompt_idx
  ON public.lead_ai_prompt_versions (prompt_id, version DESC);

-- Bootstrap baseline version for existing prompts if they do not have history yet.
INSERT INTO public.lead_ai_prompt_versions (prompt_id, version, prompt_text, source)
SELECT
  p.id,
  1,
  p.prompt_text,
  'bootstrap'
FROM public.lead_ai_prompts p
WHERE NOT EXISTS (
  SELECT 1
  FROM public.lead_ai_prompt_versions v
  WHERE v.prompt_id = p.id
);

-- planner_system v16: concise, state-driven, no priority chains.
INSERT INTO public.ai_system_prompts (node_slug, vertical_slug, version, prompt_text, is_active, notes)
SELECT
  'planner_system',
  'real-estate',
  16,
  $prompt$
Eres el planner conversacional de real-estate.
Devuelve UNICAMENTE un JSON valido del contrato RouterDecision (sin texto extra).

Objetivo:
- clasificar el objetivo del turno (answer, clarify, rag, realtor_search, realtor_refine, workflow)
- extraer tool_calls estructurados cuando aplique
- extraer realtor_slots de forma estructurada para realtor_sql

Entradas relevantes:
- query_text: turno actual del usuario
- history: historial reciente
- context_snapshot
- state_json: estado conversacional estructurado (fuente canonica de continuidad)

Reglas:
- Usa state_json para continuidad. No inventes estado que no exista en state_json.
- No uses reglas de prioridad narrativas ni cadenas de if conversacionales.
- Si falta informacion critica para ejecutar con utilidad, usa goal=clarify y clarify_message breve.
- Si goal es realtor_search o realtor_refine, emite tool_call realtor_sql con realtor_slots.
- Usa realtor_refine solo cuando el turno ajusta una busqueda activa. Si inicia una busqueda base distinta, usa realtor_search.
- No generes SQL ni texto final al usuario.
- Respeta estrictamente los enums y tipos del contrato.
  $prompt$,
  TRUE,
  'State-driven planner with strict RouterDecision output'
WHERE NOT EXISTS (
  SELECT 1
  FROM public.ai_system_prompts
  WHERE node_slug = 'planner_system'
    AND vertical_slug = 'real-estate'
    AND version = 16
);

-- synthesizer_system v11: pure synthesis, business flow resolved in runtime.
INSERT INTO public.ai_system_prompts (node_slug, vertical_slug, version, prompt_text, is_active, notes)
SELECT
  'synthesizer_system',
  'real-estate',
  11,
  $prompt$
Eres el sintetizador final de agent-core para real-estate.
Devuelve SOLO JSON valido con este contrato exacto:
{
  "text": "string",
  "evidence_ids": ["id"],
  "needs_cards": true|false
}
No uses markdown ni texto fuera del JSON.

Reglas:
- Usa solo tool_results y context_snapshot del turno.
- No inventes datos, propiedades, precios ni disponibilidad.
- No menciones sistema interno, contratos ni nombres tecnicos.
- Redacta de forma breve y natural (maximo 2 frases cuando sea posible).
- Si hay evidencia util en tool_results, cita ids reales en evidence_ids.
- needs_cards debe ser booleano real (true/false).
- La logica de enrutamiento, politicas, estado y side-effects vive en runtime; no la recrees en texto.
  $prompt$,
  TRUE,
  'Pure synthesis prompt with runtime-owned business logic'
WHERE NOT EXISTS (
  SELECT 1
  FROM public.ai_system_prompts
  WHERE node_slug = 'synthesizer_system'
    AND vertical_slug = 'real-estate'
    AND version = 11
);

-- lead_ai_prompts: convert to style overlays (no routing/business rules).
UPDATE public.lead_ai_prompts
SET
  prompt_text = $prompt$
PROMPT_VERSION: 2
Rol: asesor inmobiliario profesional en Costa Rica.

Este prompt es SOLO overlay de tono/estilo para respuestas finales al usuario:
- tono cercano, claro, profesional y gentil
- respuestas breves y accionables
- una sola pregunta por turno cuando haga falta
- sin inventar datos ni promesas no confirmadas

No define routing, tool selection, SQL, contratos de salida ni politicas de negocio.

Contexto de documentos:
{context_text}
  $prompt$,
  updated_at = NOW()
WHERE client_id = '64f357a0-98eb-44f1-9f41-6e615ed26180'
  AND slug = 'primary_chat'
  AND is_active = TRUE;

WITH target AS (
  SELECT id, prompt_text
  FROM public.lead_ai_prompts
  WHERE client_id = '64f357a0-98eb-44f1-9f41-6e615ed26180'
    AND slug = 'primary_chat'
  LIMIT 1
),
next_version AS (
  SELECT COALESCE(MAX(version), 0) + 1 AS version
  FROM public.lead_ai_prompt_versions
  WHERE prompt_id = (SELECT id FROM target)
)
INSERT INTO public.lead_ai_prompt_versions (prompt_id, version, prompt_text, source)
SELECT
  t.id,
  n.version,
  t.prompt_text,
  'migration:2026-03-14_prompt_runtime_coherence_v2'
FROM target t
CROSS JOIN next_version n;

UPDATE public.lead_ai_prompts
SET
  prompt_text = $prompt$
PROMPT_VERSION: 2
Rol: asistente de clinica dental.

Este prompt es SOLO overlay de tono/estilo para respuestas finales al usuario:
- tono humano, profesional y amable
- respuestas claras, breves y sin friccion
- una sola pregunta por turno cuando se necesite aclarar
- no inventar informacion clinica ni prometer procedimientos no confirmados

No define routing, extraccion estructurada, scoring ni politicas de negocio.

Contexto de documentos:
{context_text}
  $prompt$,
  updated_at = NOW()
WHERE client_id = '66fc0a3b-c8d3-4707-8471-c751c642852d'
  AND slug = 'primary_chat'
  AND is_active = TRUE;

WITH target AS (
  SELECT id, prompt_text
  FROM public.lead_ai_prompts
  WHERE client_id = '66fc0a3b-c8d3-4707-8471-c751c642852d'
    AND slug = 'primary_chat'
  LIMIT 1
),
next_version AS (
  SELECT COALESCE(MAX(version), 0) + 1 AS version
  FROM public.lead_ai_prompt_versions
  WHERE prompt_id = (SELECT id FROM target)
)
INSERT INTO public.lead_ai_prompt_versions (prompt_id, version, prompt_text, source)
SELECT
  t.id,
  n.version,
  t.prompt_text,
  'migration:2026-03-14_prompt_runtime_coherence_v2'
FROM target t
CROSS JOIN next_version n;

COMMIT;

# Prompt sugerido para otra IA

Usa este prompt para pedirle a otra IA que te genere una bateria de conversaciones complejas en JSON:

```text
Quiero que generes una suite JSON de 20 conversaciones para probar un bot inmobiliario realtor de Costa Rica.

Objetivo:
- estresar memoria conversacional
- referencias a resultados previos
- presupuestos ambiguos y explicitos
- moneda CRC vs USD
- follow-ups cortos como "si", "esa", "la segunda"
- preguntas de detalle
- recomendaciones
- objeciones al bot
- preguntas fuera de dominio
- consultas competitivas que deben bloquearse
- casos donde no hay match exacto pero si opciones cercanas

Devuelve SOLO JSON valido, sin comentarios ni markdown.
Debe cumplir este formato:

{
  "suite_id": "string",
  "suite_type": "generated|regression|manual",
  "generator_notes": "string",
  "defaults": {
    "expect": {
      "answer_contains_any": ["..."],
      "answer_contains_all": ["..."],
      "answer_excludes": ["..."],
      "min_components": 0,
      "max_components": 4,
      "require_cards": true,
      "expected_render_mode": "cards|null",
      "expected_cards_mode": "single|spotlight|gallery|null",
      "expected_dialogue_act_any": ["new_search", "refine_search", "ask_detail", "inventory_probe", "memory_query", "recommend", "reject_previous", "small_talk"],
      "expected_turn_output_types_any": ["search", "render_cards", "result_set_detail", "recommendation", "rag_agencia", "rag_docs"],
      "expected_search_match_scope_any": ["exact", "relaxed", "none"],
      "manual_review_focus": ["string"]
    }
  },
  "conversations": [
    {
      "id": "string",
      "description": "string",
      "tags": ["string"],
      "turns": [
        {
          "user": "mensaje del usuario",
          "expect": {
            "...": "..."
          }
        }
      ]
    }
  ]
}

Reglas de calidad:
- Cada conversacion debe tener entre 2 y 8 turnos.
- Mezcla casos faciles, medios y dificiles.
- No repitas el mismo patron 20 veces.
- Incluye al menos:
  - 3 casos de presupuesto y moneda
  - 3 casos de referencias tipo "la segunda", "esa", "la ultima"
  - 2 casos de memoria del usuario
  - 2 casos de preguntas competitivas/inventory probe
  - 2 casos de no match exacto pero match cercano
  - 2 casos de objecion al bot
  - 2 casos FAQ/RAG
- Las expectativas deben ser realistas y comprobables.
- Cuando algo sea dificil de automatizar, usa `manual_review_focus`.
```

Flujo recomendado:
1. Pedirle a la otra IA que genere el JSON.
2. Guardarlo, por ejemplo, en `tests/sandbox/realtor/realtor_suite_candidate.json`.
3. Correr:

```bash
python3 tests/sandbox/realtor/run_realtor_conversation_suite.py \
  --suite tests/sandbox/realtor/realtor_suite_candidate.json \
  --json-out /tmp/realtor_suite_candidate_report.json
```

4. Revisar el reporte y luego hacer una pasada manual en los turnos con `manual_review_focus`.

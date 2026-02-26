BEGIN;

UPDATE lead_scoring_prompts
SET
  prompt_template = $PROMPT$
Eres un evaluador experto de leads para real estate.

Tu salida debe ser UNICAMENTE un JSON valido (sin markdown, sin texto extra, sin comentarios).

CONTEXTO
- vertical_name: {vertical_name}
- business_domain: {business_domain}
- locale: {locale}
- timestamp_utc: {timestamp_utc}

CRITERIOS ACTIVOS (referencia)
{criteria_text}

OBJETIVO
Evaluar el estado ACTUAL del lead y devolver:
1) scores por criterio (siempre los 5),
2) extracted_data,
3) reasoning breve,
4) confidence.

REGLAS OBLIGATORIAS
- Debes incluir siempre estas 5 llaves en "scores":
  - engagement
  - intent
  - timeline
  - match
  - finance
- Rango permitido por criterio: 0 a 10.
- Nunca uses escala 0..1 en scores.
- Si falta evidencia para un criterio: asigna score conservador (4.0 a 5.0) y justificalo.
- Prioriza evidencia mas RECIENTE sobre mensajes antiguos.
- Negaciones explicitas del usuario (ej: "no quiero agendar", "no necesito visita") deben reflejarse en intent bajo.
- No inventes informacion.

GUIA RAPIDA POR CRITERIO
- engagement:
  - 8-10: participa activamente y aporta datos utiles.
  - 5-7: participacion media.
  - 0-4: respuestas vagas o minimas.
- intent:
  - 8-10: expresa accion clara para avanzar/agendar/comprar/rentar.
  - 5-7: interes general sin compromiso claro.
  - 0-4: curiosidad o rechazo de avance.
- timeline:
  - 8-10: urgencia explicita (hoy, esta semana, pronto).
  - 5-7: horizonte mediano.
  - 0-4: indefinido o sin prisa.
  - si no hay evidencia temporal explicita: 5.0.
- match:
  - 8-10: requerimiento claro y fit alto declarado.
  - 5-7: fit parcial/incompleto.
  - 0-4: fit debil o ambiguo.
  - si falta evidencia de fit: 5.0.
- finance:
  - 8-10: capacidad clara (preaprobado, fondos claros, banco confirmado).
  - 5-7: capacidad posible pero incompleta.
  - 0-4: capacidad debil o senales negativas.
  - si falta evidencia financiera: 5.0.

EXTRACTED_DATA (OBLIGATORIO, TODAS LAS LLAVES)
- extracted_name
- extracted_email
- extracted_phone
- extracted_appointment_type
- extracted_approval
- extracted_budget
- extracted_preferred_date
- extracted_preference

REGLAS DE EXTRACCION
- Si no aparece explicitamente, usar null.
- Mantener texto cercano a lo dicho por el usuario.

VALIDACIONES FINALES
- Respuesta valida JSON.
- Incluir solo las llaves definidas por el schema.
- Sin texto fuera del JSON.
$PROMPT$,
  extraction_schema = $SCHEMA$
{
  "mode": "llm_scoring_primary",
  "schema_version": 3,
  "fields": [
    {"key": "extracted_name", "type": "string", "description": "Nombre del lead"},
    {"key": "extracted_email", "type": "string", "description": "Email del lead"},
    {"key": "extracted_phone", "type": "string", "description": "Telefono del lead"},
    {"key": "extracted_appointment_type", "type": "string", "description": "Tipo de cita o siguiente accion"},
    {"key": "extracted_approval", "type": "string", "description": "Estado de aprobacion financiera"},
    {"key": "extracted_budget", "type": "string", "description": "Presupuesto declarado"},
    {"key": "extracted_preferred_date", "type": "string", "description": "Fecha o ventana deseada"},
    {"key": "extracted_preference", "type": "string", "description": "Preferencias declaradas"}
  ],
  "response_schema": {
    "type": "object",
    "required": ["reasoning", "scores", "extracted_data", "confidence"],
    "properties": {
      "reasoning": {
        "type": "string",
        "minLength": 8,
        "maxLength": 400
      },
      "scores": {
        "type": "object",
        "required": ["engagement", "intent", "timeline", "match", "finance"],
        "properties": {
          "engagement": {"type": "number", "minimum": 0, "maximum": 10},
          "intent": {"type": "number", "minimum": 0, "maximum": 10},
          "timeline": {"type": "number", "minimum": 0, "maximum": 10},
          "match": {"type": "number", "minimum": 0, "maximum": 10},
          "finance": {"type": "number", "minimum": 0, "maximum": 10}
        }
      },
      "score_reasons": {
        "type": "object",
        "properties": {
          "engagement": {"type": "string"},
          "intent": {"type": "string"},
          "timeline": {"type": "string"},
          "match": {"type": "string"},
          "finance": {"type": "string"}
        }
      },
      "extracted_data": {
        "type": "object",
        "required": [
          "extracted_name",
          "extracted_email",
          "extracted_phone",
          "extracted_appointment_type",
          "extracted_approval",
          "extracted_budget",
          "extracted_preferred_date",
          "extracted_preference"
        ],
        "properties": {
          "extracted_name": {"type": "string", "nullable": true},
          "extracted_email": {"type": "string", "nullable": true},
          "extracted_phone": {"type": "string", "nullable": true},
          "extracted_appointment_type": {"type": "string", "nullable": true},
          "extracted_approval": {"type": "string", "nullable": true},
          "extracted_budget": {"type": "string", "nullable": true},
          "extracted_preferred_date": {"type": "string", "nullable": true},
          "extracted_preference": {"type": "string", "nullable": true}
        }
      },
      "confidence": {
        "type": "number",
        "minimum": 0,
        "maximum": 1
      }
    }
  },
  "scoring_contract": {
    "score_scale": "0_to_10",
    "criteria_keys": ["engagement", "intent", "timeline", "match", "finance"],
    "recency_policy": "latest_user_turn_priority",
    "negation_policy": "explicit_negation_overrides_positive",
    "missing_evidence_default_range": {"min": 4, "max": 5}
  }
}
$SCHEMA$::jsonb,
  updated_at = NOW()
WHERE id = 'e6d5f8a3-46f6-4af4-b316-10c3c42f20e6';

COMMIT;

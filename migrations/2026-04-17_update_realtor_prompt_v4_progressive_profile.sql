BEGIN;

UPDATE lead_scoring_prompts
SET
  prompt_template = replace(
    replace(
      prompt_template,
      $OLD_NEGATION$
- Negaciones explicitas del usuario (ej: "no quiero agendar", "no necesito visita") deben reflejarse en intencion bajo.
$OLD_NEGATION$,
      $NEW_NEGATION$
- Negaciones explicitas del usuario (ej: "no quiero agendar", "no necesito visita") deben reflejarse en extracted_appointment_intent = "negative" y tipo_cita = null.
- No bajes automaticamente intencion si el interes comercial sigue alto (ej: quiere mas fotos o comparar antes de visitar).
$NEW_NEGATION$
    ),
    $OLD_SLOT_RULE$
- Si el usuario acaba de entregar `nombre`, `email`, `telefono` u otro dato de lead en este mismo turno, no encadenes automaticamente el siguiente campo.
$OLD_SLOT_RULE$,
    $NEW_SLOT_RULE$
- Si appointment_intent = "negative" con motivo contextual (ej: "primero quiero ver mas fotos"), captura ese motivo en `extracted_preference` cuando aplique y no repreguntes visita/tipo_cita dentro del mismo hilo, salvo que el usuario reactive ese tema explicitamente.
- Si el usuario acaba de entregar `nombre`, `email`, `telefono` u otro dato de lead en este mismo turno, no encadenes automaticamente el siguiente campo.
$NEW_SLOT_RULE$
  ),
  extraction_schema = jsonb_set(
    jsonb_set(
      extraction_schema,
      '{scoring_contract,progressive_profile}',
      $PROFILE_JSON$
{
  "journey_source": "search_filters.operacion",
  "journey_field_orders": {
    "sale": ["presupuesto", "aprobacion", "fecha_preferida", "appointment_intent", "tipo_cita", "contacto", "email", "telefono", "preferencias", "nombre"],
    "rent": ["fecha_preferida", "presupuesto", "appointment_intent", "tipo_cita", "contacto", "email", "telefono", "preferencias", "nombre"],
    "default": ["appointment_intent", "tipo_cita", "contacto", "email", "telefono", "presupuesto", "aprobacion", "fecha_preferida", "preferencias", "nombre"]
  },
  "contact_policy": {
    "default": "channel_aware",
    "by_channel": {
      "meta_whatsapp": "phone_first",
      "whatsapp": "phone_first",
      "telegram": "phone_first",
      "webchat": "email_first"
    }
  }
}
$PROFILE_JSON$::jsonb,
      true
    ),
    '{scoring_contract,negation_policy}',
    '"appointment_intent_negative_not_equal_intent_negative"'::jsonb,
    true
  ),
  updated_at = NOW()
WHERE id = '190dc860-9d37-4883-a6f4-c3019fdd882e'
  AND version = 4;

COMMIT;

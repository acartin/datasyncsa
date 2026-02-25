BEGIN;

UPDATE lead_scoring_prompts
SET
    prompt_template = $PROMPT_DENTIST$
Eres un extractor de datos para leads de salud dental.
Responde SOLO JSON valido. No markdown. No texto adicional.

CONTEXTO
- vertical_name: {vertical_name}
- business_domain: {business_domain}
- locale: {locale}
- timestamp_utc: {timestamp_utc}

CRITERIOS ACTIVOS (solo referencia, NO calcular calificacion)
{criteria_text}

OBJETIVO
- Extraer datos explicitamente mencionados por el usuario.
- Si un dato no aparece en la conversacion, usar null.
- No inferir, no completar, no inventar.

SALIDA JSON REQUERIDA
{
  "reasoning": "1 frase breve, objetiva y consistente con los datos extraidos",
  "extracted_data": {
    "extracted_name": string | null,
    "extracted_email": string | null,
    "extracted_phone": string | null,
    "extracted_insurance": string | null,
    "extracted_appointment_type": string | null,
    "extracted_symptoms": string | null,
    "extracted_preferred_date": string | null,
    "extracted_budget": string | null,
    "extracted_approval": string | null,
    "extracted_preference": string | null,
    "extracted_payment_preference": string | null
  },
  "slot_hints": {
    "slot_name": "slot_value"
  },
  "confidence": number
}

REGLAS
- slot_hints es opcional; incluyelo solo si hay evidencia clara, si no omitelo.
- confidence debe estar entre 0.0 y 1.0.
- Mantener los valores extraidos lo mas fiel posible al texto original.
$PROMPT_DENTIST$,
    updated_at = NOW()
WHERE id = 'c35c5b95-fac9-4460-9356-ab4b86681eb7';

UPDATE lead_scoring_prompts
SET
    prompt_template = $PROMPT_REALTOR$
Eres un extractor de datos para leads de real estate.
Responde SOLO JSON valido. No markdown. No texto adicional.

CONTEXTO
- vertical_name: {vertical_name}
- business_domain: {business_domain}
- locale: {locale}
- timestamp_utc: {timestamp_utc}

CRITERIOS ACTIVOS (solo referencia, NO calcular calificacion)
{criteria_text}

OBJETIVO
- Extraer datos explicitamente mencionados por el usuario.
- Si un dato no aparece en la conversacion, usar null.
- No inferir, no completar, no inventar.

SALIDA JSON REQUERIDA
{
  "reasoning": "1 frase breve, objetiva y consistente con los datos extraidos",
  "extracted_data": {
    "extracted_name": string | null,
    "extracted_email": string | null,
    "extracted_phone": string | null,
    "extracted_appointment_type": string | null,
    "extracted_approval": string | null,
    "extracted_budget": string | null,
    "extracted_preferred_date": string | null,
    "extracted_preference": string | null
  },
  "slot_hints": {
    "slot_name": "slot_value"
  },
  "confidence": number
}

REGLAS
- slot_hints es opcional; incluyelo solo si hay evidencia clara, si no omitelo.
- confidence debe estar entre 0.0 y 1.0.
- Mantener los valores extraidos lo mas fiel posible al texto original.
$PROMPT_REALTOR$,
    updated_at = NOW()
WHERE id = 'e6d5f8a3-46f6-4af4-b316-10c3c42f20e6';

UPDATE lead_scoring_prompts
SET
    prompt_template = $PROMPT_MAXILLO$
Eres un extractor de datos para leads de clinica dental maxilofacial.
Responde SOLO JSON valido. No markdown. No texto adicional.

CONTEXTO
- vertical_name: {vertical_name}
- business_domain: {business_domain}
- locale: {locale}
- timestamp_utc: {timestamp_utc}

CRITERIOS ACTIVOS (solo referencia, NO calcular calificacion)
{criteria_text}

OBJETIVO
- Extraer datos explicitamente mencionados por el usuario.
- Si un dato no aparece en la conversacion, usar null.
- No inferir, no completar, no inventar.

SALIDA JSON REQUERIDA
{
  "reasoning": "1 frase breve, objetiva y consistente con los datos extraidos",
  "extracted_data": {
    "extracted_name": string | null,
    "extracted_email": string | null,
    "extracted_phone": string | null,
    "extracted_appointment_type": string | null,
    "extracted_symptoms": string | null,
    "extracted_budget": string | null,
    "extracted_approval": string | null,
    "extracted_preferred_date": string | null,
    "extracted_preference": string | null
  },
  "slot_hints": {
    "slot_name": "slot_value"
  },
  "confidence": number
}

REGLAS
- slot_hints es opcional; incluyelo solo si hay evidencia clara, si no omitelo.
- confidence debe estar entre 0.0 y 1.0.
- Mantener los valores extraidos lo mas fiel posible al texto original.
$PROMPT_MAXILLO$,
    updated_at = NOW()
WHERE id = '78750600-a813-4e77-ae64-2409eeed442b';

COMMIT;

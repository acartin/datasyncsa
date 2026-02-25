BEGIN;

DO $$
DECLARE
    v_default_fields JSONB := '[
        {"key":"extracted_name","type":"string","description":"Nombre completo del lead"},
        {"key":"extracted_email","type":"string","description":"Correo electronico del lead"},
        {"key":"extracted_phone","type":"string","description":"Telefono del lead"},
        {"key":"extracted_budget","type":"string","description":"Presupuesto declarado por el lead"},
        {"key":"extracted_approval","type":"string","description":"Estado de aprobacion o financiamiento"},
        {"key":"extracted_preferred_date","type":"string","description":"Fecha o ventana preferida"},
        {"key":"extracted_preference","type":"string","description":"Preferencia de contacto"},
        {"key":"extracted_appointment_type","type":"string","description":"Tipo de cita o siguiente accion"}
    ]'::jsonb;
    v_deterministic JSONB := '{
        "slots": {
            "intent": {
                "default": "unknown",
                "rules": [
                    {"set": "ready_to_advance", "contains_any": ["agendar","agenda","cita","quiero comprar","quiero reservar","visitar","contactame","contactar","llamame","llamarme"]},
                    {"set": "interested", "contains_any": ["me interesa","interesa","quiero","busco","necesito","cotizacion","cotizar","precio","informacion"]},
                    {"set": "exploring", "contains_any": ["solo viendo","solo consultando","curiosidad","tal vez","quizas"]}
                ]
            },
            "timeline_bucket": {
                "default": "unknown",
                "rules": [
                    {"set": "immediate", "contains_any": ["hoy","manana","esta semana","urgente","ya","lo antes posible","cuanto antes"]},
                    {"set": "immediate", "source_field": "extracted_preferred_date", "contains_any": ["hoy","manana","esta semana","urgente","ya","lo antes posible","cuanto antes"]},
                    {"set": "short_term", "contains_any": ["este mes","en un mes","proximas semanas","1 mes","2 meses","3 meses"]},
                    {"set": "short_term", "source_field": "extracted_preferred_date", "contains_any": ["este mes","en un mes","proximas semanas","1 mes","2 meses","3 meses"]},
                    {"set": "mid_term", "contains_any": ["6 meses","medio ano","este ano"]},
                    {"set": "long_term", "contains_any": ["sin prisa","mas adelante","proximo ano","el otro ano"]}
                ]
            },
            "financing_readiness": {
                "default": "unknown",
                "rules": [
                    {"set": "approved", "contains_any": ["preaprob","aprobado","aprobada","credito aprobado","hipoteca aprobada","contado","cash"]},
                    {"set": "approved", "source_field": "extracted_approval", "contains_any": ["preaprob","aprobado","aprobada","credito aprobado","hipoteca aprobada","contado","cash"]},
                    {"set": "partial", "contains_any": ["credito","prestamo","hipoteca","financiar","financiacion","banco","tramitando","precalificado"]},
                    {"set": "partial", "source_field": "extracted_approval", "contains_any": ["credito","prestamo","hipoteca","financiar","financiacion","banco","tramitando","precalificado"]}
                ]
            },
            "budget_bucket": {
                "default": "unknown",
                "rules": [
                    {"set": "quantified", "source_field": "extracted_budget", "has_number": true},
                    {"set": "mentioned", "contains_any": ["presupuesto","prima","enganche","rango","monto","$","usd"]}
                ]
            }
        },
        "derived_slots": [
            {
                "slot": "urgency_level",
                "type": "map_from_slot",
                "source_slot": "timeline_bucket",
                "default": "unknown",
                "mapping": {
                    "immediate": "high",
                    "short_term": "medium",
                    "mid_term": "medium",
                    "long_term": "low",
                    "unknown": "unknown"
                }
            },
            {
                "slot": "contactability",
                "type": "count_present_fields",
                "fields": ["extracted_name","extracted_email","extracted_phone"],
                "default": "none",
                "thresholds": [
                    {"min": 2, "set": "full"},
                    {"min": 1, "set": "partial"}
                ]
            },
            {
                "slot": "data_quality",
                "type": "count_present_fields",
                "fields": ["extracted_name","extracted_email","extracted_phone","extracted_budget","extracted_approval","extracted_preferred_date","extracted_preference","extracted_appointment_type"],
                "default": "low",
                "thresholds": [
                    {"min": 5, "set": "high"},
                    {"min": 3, "set": "medium"}
                ]
            },
            {
                "slot": "engagement_level",
                "type": "engagement_blend",
                "fields": ["extracted_name","extracted_email","extracted_phone","extracted_budget","extracted_approval","extracted_preferred_date","extracted_preference","extracted_appointment_type"],
                "default": "low",
                "low_value": "low",
                "medium_value": "medium",
                "high_value": "high",
                "user_turns_medium": 2,
                "user_turns_high": 4,
                "field_count_medium": 2,
                "field_count_high": 4,
                "text_chars_medium": 250,
                "text_chars_high": 600
            },
            {
                "slot": "product_fit",
                "type": "keyword_bucket_count",
                "default": "unknown",
                "buckets": [
                    {"contains_any": ["casa","apartamento","aparta","lote","condominio","oficina","local","terreno","propiedad"]},
                    {"contains_any": ["habitacion","dormitorio","bano","parqueo","cochera","m2","metros","patio","mascota"]},
                    {"contains_any": ["san jose","heredia","alajuela","cartago","guanacaste","escazu"]},
                    {"slot_condition": {"slot": "budget_bucket", "any_of": ["mentioned","quantified"]}}
                ],
                "thresholds": [
                    {"min": 3, "set": "strong"},
                    {"min": 2, "set": "medium"},
                    {"min": 1, "set": "weak"}
                ]
            }
        ],
        "criteria_rules": {
            "intent": {
                "type": "slot_map",
                "slot": "intent",
                "default": 3.0,
                "mapping": {
                    "ready_to_advance": 9.0,
                    "interested": 7.0,
                    "exploring": 4.5,
                    "unknown": 3.0
                }
            },
            "timeline": {
                "type": "slot_map",
                "slot": "timeline_bucket",
                "default": 4.0,
                "mapping": {
                    "immediate": 9.0,
                    "short_term": 7.5,
                    "mid_term": 6.0,
                    "long_term": 3.5,
                    "unknown": 4.0
                }
            },
            "urgency": {
                "type": "slot_map",
                "slot": "urgency_level",
                "default": 4.0,
                "mapping": {
                    "high": 9.0,
                    "medium": 6.5,
                    "low": 3.5,
                    "unknown": 4.0
                }
            },
            "finance": {
                "type": "matrix",
                "slots": ["financing_readiness","budget_bucket"],
                "separator": "|",
                "default": 3.0,
                "mapping": {
                    "approved|quantified": 9.2,
                    "approved|mentioned": 8.4,
                    "approved|unknown": 7.8,
                    "partial|quantified": 7.6,
                    "partial|mentioned": 6.4,
                    "partial|unknown": 5.6,
                    "unknown|quantified": 5.2,
                    "unknown|mentioned": 4.4,
                    "unknown|unknown": 3.0
                }
            },
            "match": {
                "type": "slot_map",
                "slot": "product_fit",
                "default": 4.0,
                "mapping": {
                    "strong": 9.0,
                    "medium": 7.0,
                    "weak": 4.5,
                    "unknown": 4.0
                }
            },
            "data_quality": {
                "type": "slot_map",
                "slot": "data_quality",
                "default": 3.2,
                "mapping": {
                    "high": 9.0,
                    "medium": 6.5,
                    "low": 3.2
                }
            },
            "engagement": {
                "type": "slot_map",
                "slot": "engagement_level",
                "default": 3.0,
                "mapping": {
                    "high": 9.0,
                    "medium": 6.5,
                    "low": 3.0
                }
            }
        }
    }'::jsonb;
BEGIN
    -- Active prompts without extraction schema get default fields + deterministic rules.
    UPDATE lead_scoring_prompts
    SET extraction_schema = jsonb_build_object(
        'fields', v_default_fields,
        'deterministic_scoring', v_deterministic
    ),
    updated_at = NOW()
    WHERE is_active = true
      AND extraction_schema IS NULL;

    -- Active prompts with existing extraction schema keep their fields/properties and receive deterministic rules.
    UPDATE lead_scoring_prompts
    SET extraction_schema = jsonb_set(extraction_schema, '{deterministic_scoring}', v_deterministic, true),
        updated_at = NOW()
    WHERE is_active = true
      AND extraction_schema IS NOT NULL;
END $$;

COMMIT;

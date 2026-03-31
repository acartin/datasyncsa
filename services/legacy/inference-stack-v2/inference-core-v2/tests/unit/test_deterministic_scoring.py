from app.services.deterministic_scoring import deterministic_scoring_service


def _criteria():
    return [
        {"criterion_key": "intent", "min_score": 0, "max_score": 10},
        {"criterion_key": "timeline", "min_score": 0, "max_score": 10},
        {"criterion_key": "urgency", "min_score": 0, "max_score": 10},
        {"criterion_key": "finance", "min_score": 0, "max_score": 10},
        {"criterion_key": "match", "min_score": 0, "max_score": 10},
        {"criterion_key": "data_quality", "min_score": 0, "max_score": 10},
        {"criterion_key": "engagement", "min_score": 0, "max_score": 10},
    ]


def _deterministic_config():
    return {
        "slots": {
            "intent": {
                "default": "unknown",
                "rules": [
                    {"set": "ready_to_advance", "contains_any": ["agendar", "cita", "quiero comprar"]},
                    {"set": "interested", "contains_any": ["me interesa", "quiero", "busco"]},
                    {"set": "exploring", "contains_any": ["solo viendo"]},
                ],
            },
            "timeline_bucket": {
                "default": "unknown",
                "rules": [
                    {"set": "immediate", "contains_any": ["hoy", "esta semana", "urgente"]},
                    {"set": "short_term", "contains_any": ["este mes", "1 mes", "2 meses"]},
                ],
            },
            "financing_readiness": {
                "default": "unknown",
                "rules": [
                    {"set": "approved", "contains_any": ["preaprobado", "credito aprobado"]},
                    {"set": "partial", "contains_any": ["credito", "banco"]},
                ],
            },
            "budget_bucket": {
                "default": "unknown",
                "rules": [
                    {"set": "quantified", "source_field": "extracted_budget", "has_number": True},
                    {"set": "mentioned", "contains_any": ["presupuesto", "monto"]},
                ],
            },
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
                    "unknown": "unknown",
                },
            },
            {
                "slot": "contactability",
                "type": "count_present_fields",
                "fields": ["extracted_name", "extracted_email", "extracted_phone"],
                "default": "none",
                "thresholds": [{"min": 2, "set": "full"}, {"min": 1, "set": "partial"}],
            },
            {
                "slot": "data_quality",
                "type": "count_present_fields",
                "fields": ["extracted_name", "extracted_email", "extracted_phone", "extracted_budget"],
                "default": "low",
                "thresholds": [{"min": 4, "set": "high"}, {"min": 2, "set": "medium"}],
            },
            {
                "slot": "engagement_level",
                "type": "engagement_blend",
                "fields": ["extracted_name", "extracted_email", "extracted_phone", "extracted_budget"],
                "default": "low",
                "low_value": "low",
                "medium_value": "medium",
                "high_value": "high",
                "user_turns_medium": 2,
                "user_turns_high": 4,
                "field_count_medium": 2,
                "field_count_high": 3,
                "text_chars_medium": 120,
                "text_chars_high": 300,
            },
            {
                "slot": "product_fit",
                "type": "keyword_bucket_count",
                "default": "unknown",
                "buckets": [
                    {"contains_any": ["casa", "apartamento"]},
                    {"contains_any": ["habitaciones", "parqueo"]},
                    {"contains_any": ["heredia", "san jose"]},
                    {"slot_condition": {"slot": "budget_bucket", "any_of": ["mentioned", "quantified"]}},
                ],
                "thresholds": [{"min": 3, "set": "strong"}, {"min": 2, "set": "medium"}, {"min": 1, "set": "weak"}],
            },
        ],
        "criteria_rules": {
            "intent": {
                "type": "slot_map",
                "slot": "intent",
                "default": 3.0,
                "mapping": {"ready_to_advance": 9.0, "interested": 7.0, "exploring": 4.5, "unknown": 3.0},
            },
            "timeline": {
                "type": "slot_map",
                "slot": "timeline_bucket",
                "default": 4.0,
                "mapping": {"immediate": 9.0, "short_term": 7.5, "unknown": 4.0},
            },
            "urgency": {
                "type": "slot_map",
                "slot": "urgency_level",
                "default": 4.0,
                "mapping": {"high": 9.0, "medium": 6.5, "unknown": 4.0},
            },
            "finance": {
                "type": "matrix",
                "slots": ["financing_readiness", "budget_bucket"],
                "separator": "|",
                "default": 3.0,
                "mapping": {
                    "approved|quantified": 9.2,
                    "partial|quantified": 7.6,
                    "partial|mentioned": 6.4,
                    "unknown|unknown": 3.0,
                },
            },
            "match": {
                "type": "slot_map",
                "slot": "product_fit",
                "default": 4.0,
                "mapping": {"strong": 9.0, "medium": 7.0, "weak": 4.5, "unknown": 4.0},
            },
            "data_quality": {
                "type": "slot_map",
                "slot": "data_quality",
                "default": 3.2,
                "mapping": {"high": 9.0, "medium": 6.5, "low": 3.2},
            },
            "engagement": {
                "type": "slot_map",
                "slot": "engagement_level",
                "default": 3.0,
                "mapping": {"high": 9.0, "medium": 6.5, "low": 3.0},
            },
        },
    }


def test_deterministic_scoring_high_signal_conversation():
    conversation = (
        "Usuario: Hola, me interesa una casa en Heredia con 3 habitaciones.\n"
        "Usuario: Quiero agendar una cita esta semana, cuanto antes.\n"
        "Usuario: Mi presupuesto es de 250000 y ya tengo credito preaprobado.\n"
        "Usuario: Me llamo Ana Perez, mi correo es ana@example.com y mi telefono es 8888-9999."
    )
    extracted = {
        "extracted_name": "Ana Perez",
        "extracted_email": "ana@example.com",
        "extracted_phone": "8888-9999",
        "extracted_budget": "250000",
        "extracted_approval": "credito preaprobado",
        "extracted_preferred_date": "esta semana",
    }

    result = deterministic_scoring_service.evaluate(
        conversation_text=conversation,
        extracted_data=extracted,
        criteria=_criteria(),
        deterministic_config=_deterministic_config(),
    )

    slots = result["slot_state"]
    assert slots["intent"] == "ready_to_advance"
    assert slots["timeline_bucket"] in {"immediate", "short_term"}
    assert slots["financing_readiness"] == "approved"
    assert slots["budget_bucket"] == "quantified"
    assert slots["contactability"] == "full"
    assert slots["product_fit"] in {"medium", "strong"}

    scores = result["scores"]
    assert scores["intent"] >= 8.0
    assert scores["finance"] >= 8.0
    assert scores["data_quality"] >= 6.0
    assert scores["engagement"] >= 6.0


def test_deterministic_scoring_low_signal_defaults_to_conservative_scores():
    conversation = "Usuario: Hola, solo estoy viendo opciones."

    result = deterministic_scoring_service.evaluate(
        conversation_text=conversation,
        extracted_data={},
        criteria=_criteria(),
        deterministic_config=_deterministic_config(),
    )

    slots = result["slot_state"]
    assert slots["contactability"] == "none"
    assert slots["financing_readiness"] == "unknown"
    assert slots["data_quality"] == "low"

    scores = result["scores"]
    assert 0 <= scores["intent"] <= 6
    assert 0 <= scores["finance"] <= 6
    assert 0 <= scores["engagement"] <= 6

"""Hybrid in-memory lead scoring helpers (LLM evaluation + deterministic safeguards)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from services.ai_runtime.domain.contracts import LeadExtracted
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.prompts import PromptPayload
from services.ai_runtime.domain.state import (
    BaseGraphState,
    LeadAdvisorState,
    SCORING_CRITERION_ALIASES,
    SCORING_FIELD_ALIASES,
)
from services.ai_runtime.graph._shared.prompt_context import summarize_messages_for_prompt


DEFAULT_SCORING_TEMPLATE = """
Eres un evaluador experto de leads para {vertical_name}.

Tu salida debe ser UNICAMENTE un JSON valido (sin markdown, sin texto extra, sin comentarios).

CONTEXTO
- business_domain: {business_domain}
- locale: {locale}
- timestamp_utc: {timestamp_utc}

CRITERIOS ACTIVOS (referencia)
{criteria_text}

EXTRACTION_DATA (referencia)
{extraction_text}

OBJETIVO
Evalua el estado actual del lead y devuelve:
1) scores por criterio,
2) extracted_data,
3) score_reasons por criterio,
4) reasoning breve,
5) confidence.

REGLAS
- Rango permitido por criterio: 0 a 10.
- Si falta evidencia para un criterio, usa score bajo por desconocimiento (1.0 a 2.0) y justificacion breve.
- Si hay negacion explicita reciente, reflejala en score bajo y en la razon.
- Prioriza evidencia mas reciente sobre mensajes antiguos.
- No inventes informacion.
""".strip()

_SCORING_CONTEXT_CACHE_TTL_SECONDS = 1800
# Explicit cache creation for Gemini Flash-Lite is rejected below ~2048 tokens. We use a
# conservative char threshold to avoid repeated provider-side create failures on smaller prompts.
_SCORING_EXPLICIT_CACHE_MIN_STABLE_CHARS = 8000
_SCORING_DYNAMIC_TIMESTAMP_SENTINEL = "see dynamic_context.timestamp_utc"

_HIGH_URGENCY_HINTS = (
    "hoy",
    "manana",
    "esta semana",
    "este fin de semana",
    "este finde",
    "cuanto antes",
    "lo antes posible",
    "de inmediato",
    "inmediatamente",
    "urgente",
    "urgencia",
    "pronto",
)
_MEDIUM_URGENCY_HINTS = (
    "este mes",
    "fin de mes",
    "antes de fin de mes",
    "proximo mes",
    "este trimestre",
    "en unas semanas",
    "en unos dias",
)
_WEEKDAY_PATTERN = re.compile(
    r"\b(este|proximo)\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b"
)
_NEGATIVE_APPOINTMENT_HINTS = (
    "no quiero agendar",
    "no deseo agendar",
    "no necesito agendar",
    "todavia no",
    "aun no",
    "prefiero no agendar",
    "solo estoy comparando",
)


def _normalize_key(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_text(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return ""
    normalized = unicodedata.normalize("NFKD", candidate)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _clamp(value: float, *, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _is_meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip()
        return bool(normalized and normalized.lower() not in {"null", "none", "n/a", "unknown", "desconocido"})
    if isinstance(value, list):
        return bool(value)
    return True


def _criterion_aliases(criterion_key: str) -> list[str]:
    normalized = _normalize_key(criterion_key)
    aliases: list[str] = [normalized]
    for canonical, values in SCORING_CRITERION_ALIASES.items():
        normalized_values = [_normalize_key(item) for item in values]
        if normalized == canonical or normalized in normalized_values:
            for item in [canonical, *normalized_values]:
                if item not in aliases:
                    aliases.append(item)
            break
    return aliases


def _extract_score_and_reason(
    *,
    criterion_key: str,
    raw_scores: dict[str, Any],
    raw_reasons: dict[str, str],
) -> tuple[float | None, str | None]:
    for alias in _criterion_aliases(criterion_key):
        if alias not in raw_scores:
            continue
        raw_value = raw_scores.get(alias)
        reason_text = raw_reasons.get(alias)
        parsed_score: float | None = None
        if isinstance(raw_value, dict):
            parsed_score = _coerce_float(raw_value.get("score"))
            if parsed_score is None:
                parsed_score = _coerce_float(raw_value.get("value"))
            if not reason_text:
                reason_candidate = raw_value.get("reason") or raw_value.get("explanation")
                if isinstance(reason_candidate, str) and reason_candidate.strip():
                    reason_text = reason_candidate.strip()
        else:
            parsed_score = _coerce_float(raw_value)
        if parsed_score is not None or reason_text:
            return parsed_score, reason_text
    return None, None


def _resolve_default_from_cfg(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        direct = _coerce_float(value.get("value"))
        if direct is not None:
            return direct
        range_min = _coerce_float(value.get("min"))
        range_max = _coerce_float(value.get("max"))
        if range_min is not None and range_max is not None:
            return (range_min + range_max) / 2.0
    return None


def _resolve_missing_default(
    *,
    criterion_key: str,
    scoring_contract: dict[str, Any],
    lower: float,
    upper: float,
) -> float:
    by_criterion = scoring_contract.get("missing_score_defaults_by_criterion")
    if isinstance(by_criterion, dict):
        for alias in _criterion_aliases(criterion_key):
            resolved = _resolve_default_from_cfg(by_criterion.get(alias))
            if resolved is not None:
                return _clamp(resolved, lower=lower, upper=upper)

    range_cfg = scoring_contract.get("missing_evidence_default_range")
    resolved = _resolve_default_from_cfg(range_cfg)
    if resolved is not None:
        return _clamp(resolved, lower=lower, upper=upper)
    return _clamp(1.5, lower=lower, upper=upper)


def _format_criteria_text(advisor_state: LeadAdvisorState) -> str:
    profile = advisor_state.scoring_profile
    if profile is None:
        return "- no criteria configured"
    lines: list[str] = []
    for index, criterion in enumerate(profile.criteria, start=1):
        key = _normalize_key(criterion.key)
        if not key:
            continue
        label = str(criterion.label or key).strip()
        lines.append(
            f"{index}. {key} ({float(criterion.min_score):.0f}-{float(criterion.max_score):.0f}) "
            f"peso={float(criterion.weight):.1f} - {label}"
        )
    return "\n".join(lines) if lines else "- no criteria configured"


def _format_extraction_text(advisor_state: LeadAdvisorState) -> str:
    profile = advisor_state.scoring_profile
    if profile is None:
        return "- no extraction fields configured"
    lines: list[str] = []
    for field in profile.extraction_fields:
        key = _normalize_key(field.key)
        if not key:
            continue
        required = "required" if field.required else "optional"
        lines.append(f"- {key} ({required}, type={field.value_type})")
    return "\n".join(lines) if lines else "- no extraction fields configured"


def _render_prompt_template(template: str, values: dict[str, str]) -> str:
    candidate = str(template or "").strip()
    if not candidate:
        candidate = DEFAULT_SCORING_TEMPLATE
    try:
        return candidate.format(**values)
    except KeyError:
        escaped = candidate.replace("{", "{{").replace("}", "}}")
        for key in values:
            escaped = escaped.replace("{{" + key + "}}", "{" + key + "}")
        return escaped.format(**values)


def _build_scoring_output_contract(advisor_state: LeadAdvisorState) -> dict[str, Any]:
    criteria_keys = [key for key in advisor_state.target_criteria if _normalize_key(key)]
    extracted_keys = [key for key in advisor_state.target_fields if _normalize_key(key)]
    canonical_scores = {
        key: {
            "score": "number 0..10",
            "reason": "string breve y concreta",
        }
        for key in criteria_keys
    }
    canonical_extracted = {
        key: "valor extraido o null si no hay evidencia suficiente"
        for key in extracted_keys
    }
    return {
        "top_level_keys": [
            "scores",
            "extracted_data",
            "score_reasons",
            "reasoning",
            "confidence",
            "slot_hints",
        ],
        "scores_rules": {
            "only_target_criteria": criteria_keys,
            "range": "0..10",
            "shape": canonical_scores,
        },
        "extracted_data_rules": {
            "only_target_fields": extracted_keys,
            "shape": canonical_extracted,
        },
        "score_reasons_rules": {
            "same_keys_as_scores": True,
            "shape": {key: "string breve" for key in criteria_keys},
        },
        "reasoning_rule": "string breve",
        "confidence_rule": "number 0..1",
        "slot_hints_rule": {
            "shape": {
                "next_field": "campo canonico opcional",
                "question": "pregunta sugerida opcional",
            }
        },
    }


def _build_scoring_reference_payload(
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
) -> dict[str, Any]:
    profile = advisor_state.scoring_profile
    criteria_aliases = {
        key: list(SCORING_CRITERION_ALIASES.get(_normalize_key(key), (_normalize_key(key),)))
        for key in advisor_state.target_criteria
        if _normalize_key(key)
    }
    canonical_fields = {
        field.key: field.model_dump(mode="json")
        for field in list(profile.extraction_fields or []) if profile and str(field.key or "").strip()
    }
    return {
        "vertical": graph_state.vertical,
        "profile_metadata": {
            "vertical_id": profile.vertical_id if profile else None,
            "model_id": profile.model_id if profile else None,
            "model_version": profile.model_version if profile else None,
            "prompt_id": profile.prompt_id if profile else None,
            "prompt_version": profile.prompt_version if profile else None,
        },
        "criteria_config": [criterion.model_dump(mode="json") for criterion in list(profile.criteria or [])] if profile else [],
        "extraction_fields_config": canonical_fields,
        "scoring_contract": dict(profile.scoring_contract or {}) if profile else {},
        "criterion_aliases": criteria_aliases,
        "field_aliases": dict(SCORING_FIELD_ALIASES),
        "output_contract": _build_scoring_output_contract(advisor_state),
    }


def _build_scoring_stable_prefix(
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
) -> str:
    profile = advisor_state.scoring_profile
    template = profile.prompt_template if profile and profile.prompt_template else DEFAULT_SCORING_TEMPLATE
    values = {
        "vertical_name": graph_state.vertical,
        "business_domain": str(graph_state.tenant_config.metadata.get("business_domain") or "real_estate"),
        "locale": str(graph_state.tenant_config.metadata.get("locale") or "es-CR"),
        "timestamp_utc": _SCORING_DYNAMIC_TIMESTAMP_SENTINEL,
        "criteria_text": _format_criteria_text(advisor_state),
        "extraction_text": _format_extraction_text(advisor_state),
    }
    stable_prompt = _render_prompt_template(template, values)
    reference_payload = _build_scoring_reference_payload(graph_state, advisor_state)
    reference_block = json.dumps(reference_payload, ensure_ascii=True, indent=2, default=str)
    sections = [
        stable_prompt,
        (
            "CONFIGURACION_CANONICA_JSON\n"
            "Usa esta configuracion como fuente de verdad para los nombres canonicos, los aliases y la forma exacta del JSON de salida.\n"
            f"{reference_block}"
        ),
    ]
    return "\n\n".join(section for section in sections if section).strip()


def _build_scoring_cache_key(stable_prefix: str) -> str:
    return hashlib.sha256(stable_prefix.encode("utf-8")).hexdigest()


def _property_summary(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None
    if hasattr(item, "model_dump"):
        item = item.model_dump(mode="json")
    if not isinstance(item, dict):
        return None
    features = item.get("features") if isinstance(item.get("features"), dict) else {}
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    return {
        "id": item.get("id"),
        "price": item.get("price"),
        "currency": item.get("currency"),
        "province": location.get("province"),
        "bedrooms_clean": features.get("bedrooms_clean"),
        "bathrooms_clean": features.get("bathrooms_clean"),
    }


def _build_scoring_prompt(
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
) -> PromptPayload:
    from services.ai_runtime.verticals import get_vertical_spec

    stable_prefix = _build_scoring_stable_prefix(graph_state, advisor_state)
    policy = get_vertical_spec(graph_state.vertical).policy
    required_fields = list(advisor_state.required_fields or advisor_state.target_fields)
    completed_fields = list(advisor_state.completed_fields or [])
    pending_fields = [field for field in required_fields if field not in completed_fields]
    dynamic_context: dict[str, Any] = {
        "timestamp_utc": datetime.now(tz=UTC).isoformat(),
        "messages": summarize_messages_for_prompt(graph_state.messages, limit=10),
        "lead_extracted": advisor_state.lead_extracted.model_dump(mode="json"),
        "criteria_scores": advisor_state.criteria_scores,
        "target_criteria": advisor_state.target_criteria,
        "required_fields": required_fields,
        "completed_fields": completed_fields,
        "pending_fields": pending_fields,
        "capture_exposure_count": advisor_state.capture_exposure_count,
        "capture_unlocked": advisor_state.capture_exposure_count >= 2,
        "current_dialogue_act": graph_state.turn_analysis.dialogue_act if graph_state.turn_analysis else None,
        "current_turn_output_types": [str(item.get("type") or "") for item in graph_state.turn_outputs],
        "last_turn_dialogue_act": graph_state.last_turn_dialogue_act,
        "last_turn_output_types": list(graph_state.last_turn_output_types or []),
        "last_turn_search_summary": graph_state.last_turn_search_summary,
    }
    search_context = policy.snapshot_search_context(graph_state)
    if search_context:
        dynamic_context["search_context"] = search_context
    reference_candidates = policy.resolve_reference_candidates(graph_state)
    if reference_candidates:
        dynamic_context["reference_candidates_summary"] = [
            summary
            for summary in (_property_summary(item) for item in list(reference_candidates)[:4])
            if summary is not None
        ]
    dynamic_context = json.dumps(
        dynamic_context,
        ensure_ascii=True,
        indent=2,
        default=str,
    )
    full_prompt = "\n\n".join([stable_prefix, dynamic_context]).strip()
    cacheable = len(stable_prefix) >= _SCORING_EXPLICIT_CACHE_MIN_STABLE_CHARS
    return PromptPayload(
        node_type="lead_scoring_evaluator",
        stable_prefix=stable_prefix,
        dynamic_context=dynamic_context,
        full_prompt=full_prompt,
        cacheable=cacheable,
        cache_namespace="lead_scoring_evaluator" if cacheable else None,
        cache_key=_build_scoring_cache_key(stable_prefix) if cacheable else None,
        cache_ttl_seconds=_SCORING_CONTEXT_CACHE_TTL_SECONDS if cacheable else 0,
    )


def _normalize_extracted_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized: dict[str, Any] = {}
    updated_fields: list[str] = []
    for raw_key, raw_value in payload.items():
        key = SCORING_FIELD_ALIASES.get(_normalize_key(raw_key), _normalize_key(raw_key))
        if not key:
            continue
        if key == "presupuesto":
            budget = _coerce_float(raw_value)
            if budget is None:
                continue
            normalized[key] = float(budget)
            updated_fields.append(key)
            continue
        if key == "preferencias":
            if isinstance(raw_value, str):
                value = raw_value.strip()
                if value:
                    normalized[key] = [value]
                    updated_fields.append(key)
                continue
            if isinstance(raw_value, list):
                values = [str(item).strip() for item in raw_value if str(item).strip()]
                if values:
                    normalized[key] = values
                    updated_fields.append(key)
                continue
            continue
        if key == "appointment_intent":
            if not isinstance(raw_value, str):
                continue
            value = raw_value.strip().lower()
            if not value:
                continue
            if value not in {"positive", "negative", "uncertain"}:
                value = "uncertain"
            normalized[key] = value
            updated_fields.append(key)
            continue
        if not _is_meaningful(raw_value):
            continue
        if isinstance(raw_value, str):
            normalized[key] = raw_value.strip()
        else:
            normalized[key] = raw_value
        updated_fields.append(key)

    if normalized.get("appointment_intent") == "negative":
        normalized["tipo_cita"] = None
    return normalized, updated_fields


def _merge_extracted(base: LeadExtracted, incoming: dict[str, Any]) -> LeadExtracted:
    payload = base.model_dump(mode="json")
    for key, value in incoming.items():
        if key == "tipo_cita" and value is None:
            payload[key] = None
            continue
        if value in (None, "", []):
            continue
        if key == "preferencias":
            current = payload.get("preferencias") or []
            merged = [str(item).strip() for item in current if str(item).strip()]
            for item in value if isinstance(value, list) else []:
                candidate = str(item).strip()
                if candidate and candidate not in merged:
                    merged.append(candidate)
            payload[key] = merged
            continue
        payload[key] = value
    return LeadExtracted.model_validate(payload)


def _timeline_floor_from_text(value: Any) -> float | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    if any(hint in normalized for hint in _HIGH_URGENCY_HINTS):
        return 8.0
    if any(hint in normalized for hint in _MEDIUM_URGENCY_HINTS):
        return 6.0
    if _WEEKDAY_PATTERN.search(normalized):
        return 6.0
    return None


def _intent_floor_from_context(
    *,
    message: Any,
    appointment_intent: Any,
    fecha_preferida: Any,
) -> float | None:
    normalized_message = _normalize_text(message)
    normalized_intent = _normalize_text(appointment_intent)
    normalized_date = _normalize_text(fecha_preferida)

    if normalized_intent == "negative":
        return None
    if normalized_message and any(
        hint in normalized_message
        for hint in (
            "no quiero agendar",
            "no deseo agendar",
            "todavia no",
            "aun no",
            "prefiero no agendar",
            "solo estoy comparando",
        )
    ):
        return None
    if normalized_intent == "positive":
        return 6.0
    if normalized_date:
        return 6.0
    if not normalized_message:
        return None
    if any(
        hint in normalized_message
        for hint in (
            "agendar",
            "coordinar",
            "visitar",
            "visitarla",
            "ir a verla",
            "como lo coordinamos",
            "como coordinamos",
        )
    ):
        return 6.0
    return None


def _extract_current_user_message(graph_state: BaseGraphState) -> str | None:
    for message in reversed(graph_state.messages):
        if str(getattr(message, "role", "")).strip().lower() != "user":
            continue
        content = str(getattr(message, "content", "")).strip()
        if content:
            return content
    return None


def _latest_search_output(graph_state: BaseGraphState) -> dict[str, Any] | None:
    for item in reversed(graph_state.turn_outputs):
        if str(item.get("type") or "").strip().lower() == "search":
            return item
    return None


def _apply_timeline_score_guardrail(
    *,
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    merged_scores: dict[str, float],
    merged_reasons: dict[str, str],
    merged_extracted: LeadExtracted,
    criterion_bounds: dict[str, tuple[float, float]],
) -> list[str]:
    candidate_texts = [
        _extract_current_user_message(graph_state),
        merged_extracted.fecha_preferida,
    ]
    floor: float | None = None
    source_text: str | None = None
    for item in candidate_texts:
        candidate_floor = _timeline_floor_from_text(item)
        if candidate_floor is None:
            continue
        floor = candidate_floor
        source_text = str(item).strip()
        break
    if floor is None:
        return []

    adjusted: list[str] = []
    for criterion_key in advisor_state.target_criteria:
        normalized_key = _normalize_key(criterion_key)
        if normalized_key not in {"plazo", "urgencia", "emergencia", "timeline", "urgency"}:
            continue
        lower, upper = criterion_bounds.get(normalized_key, (0.0, 10.0))
        current_score = _coerce_float(merged_scores.get(normalized_key))
        if current_score is None:
            continue
        guarded_score = _clamp(floor, lower=lower, upper=upper)
        if current_score >= guarded_score:
            continue
        merged_scores[normalized_key] = guarded_score
        previous_reason = str(merged_reasons.get(normalized_key) or "").strip()
        guardrail_reason = (
            f"Guardrail temporal: horizonte explicito detectado en '{source_text}'; "
            f"{normalized_key} ajustado a {guarded_score:.1f}."
        )
        merged_reasons[normalized_key] = (
            f"{previous_reason} {guardrail_reason}".strip()
            if previous_reason
            else guardrail_reason
        )
        adjusted.append(normalized_key)
    return adjusted


def _apply_search_result_score_guardrail(
    *,
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    merged_scores: dict[str, float],
    merged_reasons: dict[str, str],
    criterion_bounds: dict[str, tuple[float, float]],
) -> list[str]:
    latest_search = _latest_search_output(graph_state)
    if not latest_search:
        return []
    try:
        result_count = int(latest_search.get("count") or 0)
    except (TypeError, ValueError):
        result_count = 0
    if result_count <= 0:
        return []

    normalized_act = _normalize_key(getattr(graph_state.turn_analysis, "dialogue_act", None) or "")
    if normalized_act not in {"new_search", "refine_search", "select_result", "ask_detail", "compare"}:
        return []

    relaxation_applied = bool(latest_search.get("relaxation_applied"))
    floors = {
        "apertura": 6.0,
        "openness": 6.0,
        "engagement": 6.0,
        "match": 6.0 if not relaxation_applied else 5.0,
        "fit": 6.0 if not relaxation_applied else 5.0,
        "encaje": 6.0 if not relaxation_applied else 5.0,
    }
    adjusted: list[str] = []
    for criterion_key in advisor_state.target_criteria:
        normalized_key = _normalize_key(criterion_key)
        floor = floors.get(normalized_key)
        if floor is None:
            continue
        lower, upper = criterion_bounds.get(normalized_key, (0.0, 10.0))
        current_score = _coerce_float(merged_scores.get(normalized_key))
        if current_score is None:
            continue
        guarded_score = _clamp(floor, lower=lower, upper=upper)
        if current_score >= guarded_score:
            continue
        merged_scores[normalized_key] = guarded_score
        previous_reason = str(merged_reasons.get(normalized_key) or "").strip()
        basis = "busqueda con resultados visibles"
        if not relaxation_applied:
            basis = "busqueda con resultados visibles y match util"
        guardrail_reason = (
            f"Guardrail de resultado: {basis}; "
            f"{normalized_key} ajustado a {guarded_score:.1f}."
        )
        merged_reasons[normalized_key] = (
            f"{previous_reason} {guardrail_reason}".strip()
            if previous_reason
            else guardrail_reason
        )
        adjusted.append(normalized_key)
    return adjusted


def _negative_intent_ceiling_from_context(
    *,
    message: Any,
    appointment_intent: Any,
) -> float | None:
    normalized_intent = _normalize_text(appointment_intent)
    normalized_message = _normalize_text(message)
    if normalized_intent == "negative":
        return 3.0
    if normalized_message and any(hint in normalized_message for hint in _NEGATIVE_APPOINTMENT_HINTS):
        return 3.0
    return None


def _apply_negative_intent_guardrail(
    *,
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    merged_scores: dict[str, float],
    merged_reasons: dict[str, str],
    merged_extracted: LeadExtracted,
    criterion_bounds: dict[str, tuple[float, float]],
) -> list[str]:
    ceiling = _negative_intent_ceiling_from_context(
        message=_extract_current_user_message(graph_state),
        appointment_intent=merged_extracted.appointment_intent,
    )
    if ceiling is None:
        return []

    adjusted: list[str] = []
    for criterion_key in advisor_state.target_criteria:
        normalized_key = _normalize_key(criterion_key)
        if normalized_key not in {"intencion", "intent", "purchase_intent"}:
            continue
        lower, upper = criterion_bounds.get(normalized_key, (0.0, 10.0))
        current_score = _coerce_float(merged_scores.get(normalized_key))
        if current_score is None:
            continue
        guarded_score = _clamp(ceiling, lower=lower, upper=upper)
        if current_score <= guarded_score:
            continue
        merged_scores[normalized_key] = guarded_score
        previous_reason = str(merged_reasons.get(normalized_key) or "").strip()
        guardrail_reason = (
            "Guardrail de intencion negativa: se detecto una negacion explicita de agenda; "
            f"{normalized_key} ajustado a {guarded_score:.1f}."
        )
        merged_reasons[normalized_key] = (
            f"{previous_reason} {guardrail_reason}".strip()
            if previous_reason
            else guardrail_reason
        )
        adjusted.append(normalized_key)
    return adjusted


def _apply_intent_score_guardrail(
    *,
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    merged_scores: dict[str, float],
    merged_reasons: dict[str, str],
    merged_extracted: LeadExtracted,
    criterion_bounds: dict[str, tuple[float, float]],
) -> list[str]:
    floor = _intent_floor_from_context(
        message=_extract_current_user_message(graph_state),
        appointment_intent=merged_extracted.appointment_intent,
        fecha_preferida=merged_extracted.fecha_preferida,
    )
    if floor is None:
        return []

    adjusted: list[str] = []
    for criterion_key in advisor_state.target_criteria:
        normalized_key = _normalize_key(criterion_key)
        if normalized_key not in {"intencion", "intent", "purchase_intent"}:
            continue
        lower, upper = criterion_bounds.get(normalized_key, (0.0, 10.0))
        current_score = _coerce_float(merged_scores.get(normalized_key))
        if current_score is None:
            continue
        guarded_score = _clamp(floor, lower=lower, upper=upper)
        if current_score >= guarded_score:
            continue
        merged_scores[normalized_key] = guarded_score
        previous_reason = str(merged_reasons.get(normalized_key) or "").strip()
        guardrail_reason = (
            "Guardrail de intencion: se detecto una senal clara de coordinacion o visita; "
            f"{normalized_key} ajustado a {guarded_score:.1f}."
        )
        merged_reasons[normalized_key] = (
            f"{previous_reason} {guardrail_reason}".strip()
            if previous_reason
            else guardrail_reason
        )
        adjusted.append(normalized_key)
    return adjusted


async def enrich_lead_advisor_with_llm_scoring(
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    deps: GraphDependencies,
) -> tuple[LeadAdvisorState, dict[str, Any] | None, dict[str, str] | None]:
    if not advisor_state.target_criteria:
        return advisor_state, None, None

    profile = advisor_state.scoring_profile
    scoring_contract = profile.scoring_contract if profile else {}
    criterion_bounds: dict[str, tuple[float, float]] = {}
    if profile:
        for criterion in profile.criteria:
            key = _normalize_key(criterion.key)
            if key:
                criterion_bounds[key] = (
                    float(criterion.min_score),
                    float(criterion.max_score),
                )

    prompt = _build_scoring_prompt(graph_state, advisor_state)
    try:
        raw_payload = await deps.llm.score_turn(prompt)
    except Exception:
        raw_payload = {}
    if not isinstance(raw_payload, dict):
        raw_payload = {}

    raw_slot_hints = raw_payload.get("slot_hints")
    slot_hints: dict[str, str] | None = None
    if isinstance(raw_slot_hints, dict):
        suggested_field = raw_slot_hints.get("next_field")
        if suggested_field is None:
            suggested_field = raw_slot_hints.get("next_required_field")
        if suggested_field is None:
            suggested_field = raw_slot_hints.get("field_to_ask")
        if suggested_field is None:
            suggested_field = raw_slot_hints.get("ask_for_field")
        suggested_question = raw_slot_hints.get("question")
        if suggested_question is None:
            suggested_question = raw_slot_hints.get("suggested_question")
        normalized_hints: dict[str, str] = {}
        if isinstance(suggested_field, str) and suggested_field.strip():
            normalized_hints["suggested_field"] = SCORING_FIELD_ALIASES.get(
                _normalize_key(suggested_field),
                _normalize_key(suggested_field),
            )
        if isinstance(suggested_question, str) and suggested_question.strip():
            normalized_hints["suggested_question"] = suggested_question.strip()
        if normalized_hints:
            slot_hints = normalized_hints

    raw_scores = raw_payload.get("scores")
    if not isinstance(raw_scores, dict):
        raw_scores = {
            key: value
            for key, value in raw_payload.items()
            if _normalize_key(key)
            not in {"reasoning", "confidence", "score_reasons", "extracted_data", "fields", "slot_hints"}
        }
    normalized_scores = {_normalize_key(key): value for key, value in raw_scores.items()}

    raw_reason_map = raw_payload.get("score_reasons")
    if not isinstance(raw_reason_map, dict):
        raw_reason_map = {}
    normalized_reason_map = {
        _normalize_key(key): str(value).strip()
        for key, value in raw_reason_map.items()
        if isinstance(value, str) and value.strip()
    }

    merged_scores = dict(advisor_state.criteria_scores)
    merged_reasons = dict(advisor_state.criteria_reasons)
    missing_criteria: list[str] = []
    for criterion_key in advisor_state.target_criteria:
        normalized_key = _normalize_key(criterion_key)
        lower, upper = criterion_bounds.get(normalized_key, (0.0, 10.0))
        score_value, reason_value = _extract_score_and_reason(
            criterion_key=normalized_key,
            raw_scores=normalized_scores,
            raw_reasons=normalized_reason_map,
        )
        if score_value is None:
            score_value = _resolve_missing_default(
                criterion_key=normalized_key,
                scoring_contract=scoring_contract,
                lower=lower,
                upper=upper,
            )
            missing_criteria.append(normalized_key)
        score_value = _clamp(score_value, lower=lower, upper=upper)
        merged_scores[normalized_key] = score_value
        if reason_value:
            merged_reasons[normalized_key] = reason_value
        elif normalized_key not in merged_reasons:
            merged_reasons[normalized_key] = (
                f"Evidencia insuficiente para {normalized_key}; default conservador {score_value:.1f}."
                if normalized_key in missing_criteria
                else f"Score LLM para {normalized_key}."
            )

    extracted_payload = raw_payload.get("extracted_data")
    if not isinstance(extracted_payload, dict):
        fields_payload = raw_payload.get("fields")
        extracted_payload = fields_payload if isinstance(fields_payload, dict) else {}
    normalized_extracted, updated_fields = _normalize_extracted_payload(extracted_payload)
    merged_extracted = _merge_extracted(advisor_state.lead_extracted, normalized_extracted)

    reasoning = str(raw_payload.get("reasoning") or "").strip() or None
    confidence = _coerce_float(raw_payload.get("confidence"))
    if confidence is not None:
        confidence = _clamp(confidence, lower=0.0, upper=1.0)

    guardrails_applied = _apply_timeline_score_guardrail(
        graph_state=graph_state,
        advisor_state=advisor_state,
        merged_scores=merged_scores,
        merged_reasons=merged_reasons,
        merged_extracted=merged_extracted,
        criterion_bounds=criterion_bounds,
    )
    guardrails_applied.extend(
        _apply_search_result_score_guardrail(
            graph_state=graph_state,
            advisor_state=advisor_state,
            merged_scores=merged_scores,
            merged_reasons=merged_reasons,
            criterion_bounds=criterion_bounds,
        )
    )
    guardrails_applied.extend(
        _apply_negative_intent_guardrail(
            graph_state=graph_state,
            advisor_state=advisor_state,
            merged_scores=merged_scores,
            merged_reasons=merged_reasons,
            merged_extracted=merged_extracted,
            criterion_bounds=criterion_bounds,
        )
    )
    guardrails_applied.extend(
        _apply_intent_score_guardrail(
            graph_state=graph_state,
            advisor_state=advisor_state,
            merged_scores=merged_scores,
            merged_reasons=merged_reasons,
            merged_extracted=merged_extracted,
            criterion_bounds=criterion_bounds,
        )
    )

    updated_advisor = advisor_state.model_copy(
        update={
            "criteria_scores": merged_scores,
            "criteria_reasons": merged_reasons,
            "lead_extracted": merged_extracted,
            "scoring_reasoning": reasoning,
            "scoring_confidence": confidence,
            "scoring_last_updated_turn": graph_state.current_turn,
        }
    )
    scoring_output = {
        "type": "scoring_eval",
        "scores": merged_scores,
        "confidence": confidence,
        "missing_criteria": missing_criteria,
        "updated_fields": sorted(set(updated_fields)),
    }
    if reasoning:
        scoring_output["reasoning"] = reasoning
    if guardrails_applied:
        scoring_output["guardrails_applied"] = guardrails_applied
    if slot_hints:
        scoring_output["slot_hints"] = dict(slot_hints)
    return updated_advisor, scoring_output, slot_hints

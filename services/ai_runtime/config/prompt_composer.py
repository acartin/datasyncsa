"""Runtime prompt composition helpers for the AI service."""

from __future__ import annotations

import json
from typing import Any

from services.ai_runtime.domain.contracts import TenantConfig, Vertical
from services.ai_runtime.graph._shared.prompts.clarification_prompt import build_prompt as clarification_prompt
from services.ai_runtime.graph._shared.prompts.intent_detector_prompt import build_prompt as intent_detector_prompt
from services.ai_runtime.graph._shared.prompts.lazy_condition_evaluator_prompt import (
    build_prompt as lazy_condition_prompt,
)
from services.ai_runtime.graph._shared.prompts.lead_data_collector_prompt import build_prompt as lead_data_collector_prompt
from services.ai_runtime.graph._shared.prompts.reference_classifier_prompt import build_prompt as reference_classifier_prompt
from services.ai_runtime.graph._shared.prompts.vertical.healthcare.plan_prompt import PROMPT as HEALTHCARE_PLAN_PROMPT
from services.ai_runtime.graph._shared.prompts.vertical.healthcare.synthesis_prompt import (
    PROMPT as HEALTHCARE_SYNTHESIS_PROMPT,
)
from services.ai_runtime.graph._shared.prompts.vertical.legal.plan_prompt import PROMPT as LEGAL_PLAN_PROMPT
from services.ai_runtime.graph._shared.prompts.vertical.legal.synthesis_prompt import PROMPT as LEGAL_SYNTHESIS_PROMPT
from services.ai_runtime.graph._shared.prompts.vertical.realtor.plan_prompt import PROMPT as REALTOR_PLAN_PROMPT
from services.ai_runtime.graph._shared.prompts.vertical.realtor.synthesis_prompt import PROMPT as REALTOR_SYNTHESIS_PROMPT
from services.ai_runtime.graph.realtor.prompts.appointment_data_collector_prompt import (
    build_prompt as appointment_collector_prompt,
)
from services.ai_runtime.graph.realtor.prompts.comparison_synthesizer_prompt import (
    build_prompt as comparison_synthesizer_prompt,
)
from services.ai_runtime.graph.realtor.prompts.recommendation_prompt import build_prompt as recommendation_prompt
from services.ai_runtime.graph.realtor.prompts.search_filter_extractor_prompt import (
    build_prompt as search_filter_extractor_prompt,
)
from services.ai_runtime.graph.realtor.prompts.text_to_sql_prompt import build_prompt as text_to_sql_prompt


VERTICAL_PROMPTS: dict[Vertical, dict[str, str]] = {
    "realtor": {
        "plan_prompt": REALTOR_PLAN_PROMPT,
        "synthesis_prompt": REALTOR_SYNTHESIS_PROMPT,
    },
    "healthcare": {
        "plan_prompt": HEALTHCARE_PLAN_PROMPT,
        "synthesis_prompt": HEALTHCARE_SYNTHESIS_PROMPT,
    },
    "legal": {
        "plan_prompt": LEGAL_PLAN_PROMPT,
        "synthesis_prompt": LEGAL_SYNTHESIS_PROMPT,
    },
}


def load_tone_prompt(tenant_config: TenantConfig) -> str:
    return tenant_config.tone_prompt.strip()


def load_vertical_prompt(vertical: Vertical, node_type: str) -> str:
    try:
        return VERTICAL_PROMPTS[vertical][node_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported prompt node_type={node_type!r} for vertical={vertical!r}") from exc


def _render_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=True, indent=2, default=str)


def compose(
    node_type: str,
    tenant_config: TenantConfig,
    vertical: Vertical,
    context: dict[str, Any],
    *,
    include_tone: bool = True,
) -> str:
    """Compose tone + base prompt + runtime context as the canonical prompt payload."""

    tone = load_tone_prompt(tenant_config) if include_tone else ""
    if node_type in {"plan_prompt", "synthesis_prompt"}:
        base = load_vertical_prompt(vertical, node_type)
    elif node_type == "reference_classifier":
        base = reference_classifier_prompt()
    elif node_type == "intent_detector":
        base = intent_detector_prompt()
    elif node_type == "lazy_condition_evaluator":
        base = lazy_condition_prompt()
    elif node_type == "clarification":
        base = clarification_prompt()
    elif node_type == "lead_data_collector":
        base = lead_data_collector_prompt()
    elif node_type == "text_to_sql":
        base = text_to_sql_prompt()
    elif node_type == "search_filter_extractor":
        base = search_filter_extractor_prompt()
    elif node_type == "comparison_synthesizer":
        base = comparison_synthesizer_prompt()
    elif node_type == "recommendation":
        base = recommendation_prompt()
    elif node_type == "appointment_data_collector":
        base = appointment_collector_prompt()
    else:
        raise ValueError(f"Unsupported prompt node_type={node_type!r}")
    return "\n\n".join(part for part in [tone, base, _render_context(context)] if part)

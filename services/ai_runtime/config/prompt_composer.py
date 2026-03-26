"""Runtime prompt composition helpers for the AI service."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from services.ai_runtime.domain.contracts import TenantConfig, Vertical
from services.ai_runtime.domain.prompts import PromptPayload
from services.ai_runtime.graph._shared.prompts.analyze_turn_prompt import build_prompt as analyze_turn_prompt
from services.ai_runtime.graph._shared.prompts.clarification_prompt import build_prompt as clarification_prompt
from services.ai_runtime.graph._shared.prompts.intent_detector_prompt import build_prompt as intent_detector_prompt
from services.ai_runtime.graph._shared.prompts.lazy_condition_evaluator_prompt import (
    build_prompt as lazy_condition_prompt,
)
from services.ai_runtime.graph._shared.prompts.lead_data_collector_prompt import build_prompt as lead_data_collector_prompt
from services.ai_runtime.graph._shared.prompts.memory_entity_extractor_prompt import (
    build_prompt as memory_entity_extractor_prompt,
)
from services.ai_runtime.graph._shared.prompts.reference_classifier_prompt import build_prompt as reference_classifier_prompt
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

SYSTEM_NODE_SLUG_BY_TYPE = {
    "plan_prompt": "planner_system",
    "synthesis_prompt": "synthesizer_system",
}

CONTEXT_CACHEABLE_NODE_TYPES = {
    "analyze_turn",
    "synthesis_prompt",
    "clarification",
    "comparison_synthesizer",
    "recommendation",
}
DEFAULT_CONTEXT_CACHE_TTL_SECONDS = 1800


def load_tone_prompt(tenant_config: TenantConfig) -> str:
    return tenant_config.tone_prompt.strip()


def load_vertical_prompt(tenant_config: TenantConfig, vertical: Vertical, node_type: str) -> str:
    system_node_slug = SYSTEM_NODE_SLUG_BY_TYPE.get(node_type)
    if not system_node_slug:
        raise ValueError(f"Unsupported vertical prompt node_type={node_type!r} for vertical={vertical!r}")
    runtime_prompt = (tenant_config.system_prompts.get(system_node_slug) or "").strip()
    if runtime_prompt:
        return runtime_prompt
    raise ValueError(
        f"Missing system prompt slug={system_node_slug!r} for vertical={vertical!r} and client_id={tenant_config.client_id!r}"
    )


def _render_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=True, indent=2, default=str)


def compose(
    node_type: str,
    tenant_config: TenantConfig,
    vertical: Vertical,
    context: dict[str, Any],
    *,
    include_tone: bool = False,
) -> PromptPayload:
    """Compose stable instructions + runtime context as the canonical prompt payload."""

    tone = load_tone_prompt(tenant_config) if include_tone else ""
    if node_type in {"plan_prompt", "synthesis_prompt"}:
        base = load_vertical_prompt(tenant_config, vertical, node_type)
    elif node_type == "analyze_turn":
        base = "\n\n".join(
            [
                load_vertical_prompt(tenant_config, vertical, "plan_prompt"),
                analyze_turn_prompt(),
            ]
        )
    elif node_type == "reference_classifier":
        base = reference_classifier_prompt()
    elif node_type == "intent_detector":
        base = "\n\n".join(
            [
                load_vertical_prompt(tenant_config, vertical, "plan_prompt"),
                intent_detector_prompt(),
            ]
        )
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
    elif node_type == "memory_entity_extractor":
        base = memory_entity_extractor_prompt()
    elif node_type == "comparison_synthesizer":
        base = comparison_synthesizer_prompt()
    elif node_type == "recommendation":
        base = recommendation_prompt()
    elif node_type == "appointment_data_collector":
        base = appointment_collector_prompt()
    else:
        raise ValueError(f"Unsupported prompt node_type={node_type!r}")

    stable_prefix = "\n\n".join(part for part in [tone, base] if part)
    dynamic_context = _render_context(context)
    full_prompt = "\n\n".join(part for part in [stable_prefix, dynamic_context] if part)
    cache_source = "\n\n".join(part for part in [node_type, stable_prefix] if part)
    cache_key = hashlib.sha256(cache_source.encode("utf-8")).hexdigest()

    return PromptPayload(
        node_type=node_type,
        stable_prefix=stable_prefix,
        dynamic_context=dynamic_context,
        full_prompt=full_prompt,
        cacheable=node_type in CONTEXT_CACHEABLE_NODE_TYPES and bool(stable_prefix.strip()),
        cache_namespace=node_type if node_type in CONTEXT_CACHEABLE_NODE_TYPES else None,
        cache_key=cache_key,
        cache_ttl_seconds=DEFAULT_CONTEXT_CACHE_TTL_SECONDS,
    )

"""Channel-aware CTA planning built on vertical-provided semantic actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from services.ai_runtime.domain.state import BaseGraphState


DeliverySurface = Literal["none", "property_card_inline", "action_menu"]

_INTERACTIVE_CHANNELS = {"web_html", "meta_whatsapp", "meta_ig", "api"}
_CTA_BLOCKED_DIALOGUE_ACTS = {
    "small_talk",
    "memory_query",
    "faq",
    "document_query",
    "lead_capture",
}


@dataclass(frozen=True, slots=True)
class ChannelCtaProfile:
    channel: str
    max_actions: int = 3
    prefer_inline_property_card: bool = False
    allow_action_menu: bool = True


@dataclass(frozen=True, slots=True)
class CtaDeliveryPlan:
    channel: str
    surface: DeliverySurface = "none"
    title: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)


_CHANNEL_PROFILES: dict[str, ChannelCtaProfile] = {
    "web_html": ChannelCtaProfile(
        channel="web_html",
        max_actions=3,
        prefer_inline_property_card=True,
        allow_action_menu=True,
    ),
    "meta_whatsapp": ChannelCtaProfile(
        channel="meta_whatsapp",
        max_actions=3,
        prefer_inline_property_card=False,
        allow_action_menu=True,
    ),
    "meta_ig": ChannelCtaProfile(
        channel="meta_ig",
        max_actions=3,
        prefer_inline_property_card=False,
        allow_action_menu=True,
    ),
    "api": ChannelCtaProfile(
        channel="api",
        max_actions=3,
        prefer_inline_property_card=False,
        allow_action_menu=True,
    ),
}


def _latest_user_metadata(graph_state: BaseGraphState) -> dict[str, Any]:
    for message in reversed(graph_state.messages or []):
        if getattr(message, "role", None) != "user":
            continue
        return dict(getattr(message, "metadata", None) or {})
    return {}


def resolve_cta_channel(graph_state: BaseGraphState) -> str:
    metadata = _latest_user_metadata(graph_state)
    channel = str(metadata.get("channel") or "").strip().lower()
    if channel in _INTERACTIVE_CHANNELS:
        return channel
    return "api"


def _channel_profile(channel: str) -> ChannelCtaProfile:
    return _CHANNEL_PROFILES.get(channel, _CHANNEL_PROFILES["api"])


def _has_property_card_surface(graph_state: BaseGraphState) -> bool:
    ui_payload = getattr(graph_state, "ui_payload", None) or {}
    property_cards = ui_payload.get("property_cards") if isinstance(ui_payload, dict) else None
    return bool(property_cards)


def _should_display_ctas(graph_state: BaseGraphState) -> bool:
    analysis = getattr(graph_state, "turn_analysis", None)
    dialogue_act = str(getattr(analysis, "dialogue_act", "") or "").strip().lower()
    if dialogue_act in _CTA_BLOCKED_DIALOGUE_ACTS:
        return False
    if _has_property_card_surface(graph_state):
        return True
    return False


def _normalize_actions(actions: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in actions:
        if not isinstance(item, dict):
            continue
        action_id = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        if not action_id or not label or action_id in seen_ids:
            continue
        normalized.append(
            {
                "id": action_id,
                "label": label,
                "user_text": str(item.get("user_text") or label).strip(),
                "description": str(item.get("description") or "").strip() or None,
            }
        )
        seen_ids.add(action_id)
        if len(normalized) >= max(int(limit or 0), 0):
            break
    return normalized


def build_cta_delivery_plan(graph_state: BaseGraphState) -> CtaDeliveryPlan:
    from services.ai_runtime.verticals import get_vertical_spec

    channel = resolve_cta_channel(graph_state)
    profile = _channel_profile(channel)
    if not _should_display_ctas(graph_state):
        return CtaDeliveryPlan(channel=channel)

    policy = get_vertical_spec(graph_state.vertical).policy
    semantic_actions = policy.select_semantic_ctas(
        graph_state,
        channel=channel,
        limit=profile.max_actions,
    )
    actions = _normalize_actions(semantic_actions, limit=profile.max_actions)
    if not actions:
        return CtaDeliveryPlan(channel=channel)

    if profile.prefer_inline_property_card and _has_property_card_surface(graph_state):
        return CtaDeliveryPlan(
            channel=channel,
            surface="property_card_inline",
            actions=actions,
        )

    if profile.allow_action_menu:
        return CtaDeliveryPlan(
            channel=channel,
            surface="action_menu",
            title="Si querés, seguí por una de estas opciones.",
            actions=actions,
        )

    return CtaDeliveryPlan(channel=channel)


def apply_cta_delivery_plan(
    components: list[dict[str, Any]],
    plan: CtaDeliveryPlan,
) -> list[dict[str, Any]]:
    if not plan.actions or plan.surface == "none":
        return list(components)

    normalized = [dict(component) for component in components]

    if plan.surface == "property_card_inline":
        for component in normalized:
            if str(component.get("type") or "").strip().lower() != "property-card":
                continue
            component["quick_actions"] = [
                {
                    "id": action["id"],
                    "label": action["label"],
                    "user_text": action["user_text"],
                }
                for action in plan.actions
            ]
            return normalized
        return normalized

    if plan.surface == "action_menu":
        has_action_menu = any(
            str(component.get("type") or "").strip().lower() == "action-menu"
            for component in normalized
        )
        if has_action_menu:
            return normalized
        normalized.append(
            {
                "type": "action-menu",
                "title": plan.title,
                "options": [
                    {
                        "label": action["label"],
                        "payload": action["id"],
                        "action_id": action["id"],
                        "user_text": action["user_text"],
                        "description": action.get("description"),
                    }
                    for action in plan.actions
                ],
            }
        )
    return normalized

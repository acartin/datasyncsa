import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.contracts.ui_schema import UIComponent as DashboardComponent, WebIAFirstResponse


class ClientUserDashboardSchema(BaseModel):
    layout: str
    components: List[DashboardComponent]
    debug_data: Optional[dict] = None  # Added for debugging lead data in console


from app.modules.leads.router import LEADS_GRID_CONFIG_FULL

PALETTE_HIGH = "#0AB39C"
PALETTE_MEDIUM = "#E7B547"
PALETTE_LOW = "#E06A4B"
PALETTE_NEUTRAL = "#8F98A8"

def get_seller_workspace_schema(user_id: str) -> ClientUserDashboardSchema:
    # 1. Configuración del Grid (Importada de la Fuente de Verdad)
    grid_config = LEADS_GRID_CONFIG_FULL.copy() # Copia para evitar mutaciones no deseadas
    # grid_id se mantiene como 'leads-me' para compartir Vistas Guardadas


    # 2. Construcción de Componentes (Tabs)
    return ClientUserDashboardSchema(
        layout="dashboard-standard",
        components=[
            DashboardComponent(
                type="tabs",
                # Tabs.js expects 'items' array at root, not 'components'
                items=[
                    {
                        "id": "tab-overview", 
                        "label": "Inicio", 
                        "icon": "ri-home-4-line",
                        "active": True,
                        "content": [
                            DashboardComponent(
                                type="row",
                                class_="row mb-4",
                                components=[
                                    # Metric: Leads Nuevos Hoy
                                    DashboardComponent(
                                        type="col", class_="col-md-4",
                                        components=[
                                            DashboardComponent(
                                                type="card-metric",
                                                properties={
                                                    "title": "Nuevos Hoy", "value": "3", 
                                                    "icon": "ri-user-add-line", "color": "success", "trend": "Igual que ayer"
                                                }
                                            )
                                        ]
                                    ),
                                    # Metric: Tareas Pendientes
                                    DashboardComponent(
                                        type="col", class_="col-md-4",
                                        components=[
                                            DashboardComponent(
                                                type="card-metric",
                                                properties={
                                                    "title": "Tareas Pendientes", "value": "5", 
                                                    "icon": "ri-task-line", "color": "warning", "trend": "2 urgentes"
                                                }
                                            )
                                        ]
                                    ),
                                     # Metric: Mi Conversión
                                    DashboardComponent(
                                        type="col", class_="col-md-4",
                                        components=[
                                            DashboardComponent(
                                                type="card-metric",
                                                properties={
                                                    "title": "Mi Conversión", "value": "12%", 
                                                    "icon": "ri-percent-line", "color": "primary", "trend": "Buen trabajo"
                                                }
                                            )
                                        ]
                                    ),
                                ]
                            ),
                             DashboardComponent(
                                type="card", properties={"title": "Actividad Reciente"},
                                components=[
                                     DashboardComponent(
                                        type="typography", text="Aquí irá el timeline de tus interacciones...", tag="p", class_="text-muted"
                                    )
                                ]
                            )
                        ]
                    },
                    {
                        "id": "tab-leads", 
                        "label": "Mis Leads", 
                        "icon": "ri-user-star-line",
                        "content": [
                            DashboardComponent(
                                type="custom-leads-grid",
                                properties=grid_config
                            )
                        ]
                    }
                ]
            )
        ]
    )

def get_lead_detail_schema_v2_clone(
    user_id: str,
    lead_id: str,
    lead: dict,
    scoring_schema: Optional[Dict[str, Any]] = None,
) -> ClientUserDashboardSchema:
    """
    Mis Leads v2 detail schema with dynamic scoring criteria mapping.
    """
    extraction_result = _parse_extraction_result(lead)
    intent_value, intent_icon, intent_color = _resolve_appointment_intent(extraction_result)
    score_rows = _build_v2_score_rows(lead, scoring_schema)
    profile_props = _build_v2_profile_header_props(lead, intent_value, intent_icon, intent_color)

    return ClientUserDashboardSchema(
        layout="dashboard-standard",
        components=[
            DashboardComponent(
                type="back-link",
                properties={"text": "Volver", "fallback_url": "/leads_v2/", "force_fallback": True},
            ),
            DashboardComponent(
                type="profile-header",
                properties=profile_props,
            ),
            DashboardComponent(
                type="tabs",
                class_="border-0 shadow-none",
                items=_build_v2_tabs(score_rows, lead, extraction_result),
            ),
        ],
        debug_data={
            "lead_id": lead.get("id"),
            "scorecard_id": lead.get("scorecard_id"),
            "priority_label": lead.get("priority_label"),
            "score_total": lead.get("score_total"),
            "extraction_result": extraction_result,
            "score_items_detail": lead.get("score_items_detail") or [],
            "score_criteria_source": "scoring_schema" if scoring_schema else "model_criteria",
            "score_criteria_keys": [
                c.get("criterion_key")
                for c in ((scoring_schema or {}).get("criteria") or lead.get("model_criteria") or [])
                if isinstance(c, dict)
            ],
        },
    )


def _build_v2_tabs(
    score_rows: List[Dict[str, Any]],
    lead: Dict[str, Any],
    extraction_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "tab-info",
            "label": "Información",
            "icon": "ri-information-line",
            "active": True,
            "content": [
                DashboardComponent(
                    type="card",
                    class_="border-0 shadow-none",
                    components=[
                        DashboardComponent(
                            type="row",
                            class_="border-0",
                            components=[
                                DashboardComponent(type="col", size=12, components=score_rows),
                            ],
                        )
                    ],
                ).model_dump()
            ],
        },
        {
            "id": "tab-audit",
            "label": "Audit",
            "icon": "ri-file-list-3-line",
            "content": [
                DashboardComponent(
                    type="audit-split-view",
                    properties=_build_v2_audit_props(lead, extraction_result),
                ).model_dump()
            ],
        },
        {
            "id": "tab-source",
            "label": "Fuente",
            "icon": "ri-links-line",
            "content": [
                DashboardComponent(
                    type="lead-source-view",
                    properties=_build_v2_source_props(lead),
                ).model_dump()
            ],
        },
    ]


def _format_extracted_label(raw_key: str) -> str:
    key = str(raw_key or "").strip()
    if key.startswith("extracted_"):
        key = key[len("extracted_") :]
    key = key.replace("_", " ").strip()
    return key.capitalize() if key else "Campo"


def _normalize_ui_value(value: Any) -> Any:
    if value is None:
        return "-"
    if isinstance(value, (str, int, float, bool, dict, list)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _is_supported_icon_class(raw_icon: str) -> bool:
    icon = str(raw_icon or "").strip()
    if not icon:
        return False

    tokens = icon.split()
    for token in tokens:
        if token.startswith("ri-"):
            return True
        if token == "mdi" or token.startswith("mdi-"):
            return True
        if token in {"bx", "bxs", "bxl"} or token.startswith("bx-") or token.startswith("bxs-") or token.startswith("bxl-"):
            return True
        if token in {"las", "lar", "lab"} or token.startswith("la-"):
            return True
    return False


def _resolve_source_icon(source_label: Any, source_icon: Any) -> str:
    raw_icon = str(source_icon or "").strip()
    if _is_supported_icon_class(raw_icon):
        return raw_icon

    legacy_icon = raw_icon.lower()
    legacy_map = {
        "globe": "ri-seo-line",
        "facebook": "ri-facebook-fill",
        "instagram": "ri-instagram-line",
        "home": "ri-home-4-line",
        "users": "ri-user-shared-line",
        "qr-code": "ri-qr-code-line",
        "message-circle": "ri-whatsapp-line",
        "laptop": "ri-window-line",
        "heroicon-m-identification": "ri-walk-line",
    }
    if legacy_icon in legacy_map:
        return legacy_map[legacy_icon]

    label = str(source_label or "").strip().lower()
    if "google" in label and ("sem" in label or "ads" in label):
        return "ri-megaphone-line"
    if "google" in label or "seo" in label:
        return "ri-seo-line"
    if "facebook" in label:
        return "ri-facebook-fill"
    if "instagram" in label:
        return "ri-instagram-line"
    if "whatsapp" in label:
        return "ri-whatsapp-line"
    if "walk" in label:
        return "ri-walk-line"
    if "refer" in label or "referral" in label:
        return "ri-user-shared-line"
    if any(token in label for token in ("zillow", "encuentra24", "propiedad", "property")):
        return "ri-home-4-line"
    if any(token in label for token in ("website", "web", "site")):
        return "ri-window-line"
    return "ri-links-line"


def _normalize_messages(raw_messages: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_messages, str):
        try:
            parsed = json.loads(raw_messages)
            raw_messages = parsed
        except json.JSONDecodeError:
            raw_messages = []
    if not isinstance(raw_messages, list):
        return []

    messages: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_messages):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or item.get("sender") or item.get("author") or "").strip().lower()
        content = str(item.get("content") or item.get("text") or item.get("message") or "").strip()
        if not content:
            continue
        timestamp = item.get("timestamp") or item.get("created_at") or item.get("sent_at")
        messages.append(
            {
                "id": f"m-{idx}",
                "role": role or "system",
                "content": content,
                "timestamp": _normalize_ui_value(timestamp) if timestamp is not None else "",
            }
        )
    return messages


def _build_v2_audit_props(lead: Dict[str, Any], extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    extracted_fields: List[Dict[str, Any]] = []
    for key, value in extraction_result.items():
        extracted_fields.append(
            {
                "key": str(key),
                "label": _format_extracted_label(str(key)),
                "value": _normalize_ui_value(value),
            }
        )

    evidence_groups: List[Dict[str, Any]] = []
    for item in (lead.get("score_items_detail") or []):
        if not isinstance(item, dict):
            continue
        extracted_data = item.get("extracted_data")
        if not isinstance(extracted_data, dict) or not extracted_data:
            continue
        evidence_groups.append(
            {
                "criterion_key": item.get("criterion_key") or "criterio",
                "criterion_label": item.get("criterion_key") or "Criterio",
                "data": extracted_data,
            }
        )

    latest_conversation = lead.get("latest_conversation") or {}
    if not isinstance(latest_conversation, dict):
        latest_conversation = {}

    return {
        "left_title": "Extracted data",
        "right_title": "Reconstruccion del chat",
        "extracted_fields": extracted_fields,
        "evidence_groups": evidence_groups,
        "chat_messages": _normalize_messages(latest_conversation.get("messages")),
        "chat_meta": {
            "platform": latest_conversation.get("platform") or "N/A",
            "total_messages": latest_conversation.get("total_messages") or 0,
            "lead_messages": latest_conversation.get("lead_messages") or 0,
            "bot_messages": latest_conversation.get("bot_messages") or 0,
            "last_message_at": _normalize_ui_value(latest_conversation.get("last_message_at")),
            "summary": _normalize_ui_value(latest_conversation.get("summary") or ""),
        },
    }


def _build_v2_source_props(lead: Dict[str, Any]) -> Dict[str, Any]:
    source_label = _normalize_ui_value(lead.get("source_label"))
    source_icon = _resolve_source_icon(lead.get("source_label"), lead.get("source_icon"))
    click_id_value = _normalize_ui_value(lead.get("click_id"))
    click_id_type_value = _normalize_ui_value(lead.get("click_id_type"))
    brand_project_raw = lead.get("brand_project")
    brand_project_kind = "json" if isinstance(brand_project_raw, (dict, list)) else "text"

    return {
        "source_label": source_label,
        "source_icon": source_icon,
        "business_domain": _normalize_ui_value(lead.get("business_domain")),
        "click_id": click_id_value,
        "click_id_type": click_id_type_value,
        "utm_items": [
            {"key": "utm_source", "label": "UTM Source", "value": _normalize_ui_value(lead.get("utm_source")), "icon": "ri-global-line"},
            {"key": "utm_medium", "label": "UTM Medium", "value": _normalize_ui_value(lead.get("utm_medium")), "icon": "ri-shapes-line"},
            {"key": "utm_campaign", "label": "UTM Campaign", "value": _normalize_ui_value(lead.get("utm_campaign")), "icon": "ri-megaphone-line"},
            {"key": "utm_term", "label": "UTM Term", "value": _normalize_ui_value(lead.get("utm_term")), "icon": "ri-price-tag-3-line"},
            {"key": "utm_content", "label": "UTM Content", "value": _normalize_ui_value(lead.get("utm_content")), "icon": "ri-article-line"},
        ],
        "origin_items": [
            {"key": "landing_page_url", "label": "Landing URL", "value": _normalize_ui_value(lead.get("landing_page_url")), "icon": "ri-link", "kind": "url"},
            {"key": "referrer_url", "label": "Referrer URL", "value": _normalize_ui_value(lead.get("referrer_url")), "icon": "ri-route-line", "kind": "url"},
            {"key": "source_property_url", "label": "Source Property URL", "value": _normalize_ui_value(lead.get("source_property_url")), "icon": "ri-home-8-line", "kind": "url"},
            {"key": "source_property_ref", "label": "Source Property Ref", "value": _normalize_ui_value(lead.get("source_property_ref")), "icon": "ri-hashtag"},
            {"key": "click_id", "label": "Click ID", "value": click_id_value, "icon": "ri-fingerprint-line", "kind": "mono"},
            {"key": "click_id_type", "label": "Click ID Type", "value": click_id_type_value, "icon": "ri-price-tag-2-line"},
        ],
        "technical_items": [
            {"key": "ip_address", "label": "IP Address", "value": _normalize_ui_value(lead.get("ip_address")), "icon": "ri-radar-line", "kind": "mono"},
            {"key": "user_agent", "label": "User Agent", "value": _normalize_ui_value(lead.get("user_agent")), "icon": "ri-macbook-line", "kind": "mono"},
            {
                "key": "brand_project",
                "label": "Brand Project",
                "value": _normalize_ui_value(brand_project_raw),
                "icon": "ri-building-4-line",
                "kind": brand_project_kind,
            },
            {"key": "created_at", "label": "Lead Created At", "value": _normalize_ui_value(lead.get("created_at")), "icon": "ri-calendar-event-line"},
        ],
    }


def _parse_extraction_result(lead: Dict[str, Any]) -> Dict[str, Any]:
    extraction_result = lead.get("extraction_result")
    if isinstance(extraction_result, dict):
        return extraction_result
    if isinstance(extraction_result, str):
        try:
            parsed = json.loads(extraction_result)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _resolve_appointment_intent(extraction_result: Dict[str, Any]) -> tuple[str, str, str]:
    intent = (extraction_result.get("extracted_appointment_intent") or "uncertain").strip().lower()
    appointment_type = (extraction_result.get("extracted_appointment_type") or "").strip()

    if intent == "positive":
        value = "Quiere agendar"
        if appointment_type:
            value = f"Quiere agendar ({appointment_type})"
        return value, "ri-calendar-check-line", PALETTE_HIGH
    if intent == "negative":
        return "No desea agendar", "ri-calendar-close-line", PALETTE_LOW
    return "Intención no confirmada", "ri-question-line", PALETTE_MEDIUM


def _resolve_priority_color(priority_label: str) -> str:
    normalized = (priority_label or "").strip().lower()
    if not normalized:
        return PALETTE_NEUTRAL

    if normalized in {"alta", "high"} or "alta" in normalized:
        return PALETTE_HIGH
    if normalized in {"media", "medium"} or "media" in normalized:
        return PALETTE_MEDIUM
    if normalized in {"baja", "low"} or "baja" in normalized:
        return PALETTE_LOW
    return PALETTE_NEUTRAL


def _build_v2_score_rows(
    lead: Dict[str, Any],
    scoring_schema: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    score_items = lead.get("score_items_detail") or []
    if not isinstance(score_items, list):
        score_items = []

    schema_criteria = (scoring_schema or {}).get("criteria") or []
    model_criteria = schema_criteria or lead.get("model_criteria") or []
    if not isinstance(model_criteria, list):
        model_criteria = []

    score_items_by_key = {}
    for item in score_items:
        if isinstance(item, dict) and item.get("criterion_key"):
            score_items_by_key[item["criterion_key"]] = item

    rows: List[Dict[str, Any]] = []
    if model_criteria:
        sorted_criteria = sorted(
            [c for c in model_criteria if isinstance(c, dict)],
            key=lambda c: c.get("display_order", 9999),
        )
        for criterion in sorted_criteria:
            key = criterion.get("criterion_key")
            if not key:
                continue
            item = score_items_by_key.get(key, {})
            rows.append(
                DashboardComponent(
                    type="score-row",
                    properties={
                        "title": criterion.get("label") or key,
                        "score": float(item.get("score") or 0),
                        "max_score": float(criterion.get("max_score") or 100),
                        # Keep icon contract identical to grid columns (criterion icon).
                        "icon": criterion.get("icon") or "ri-star-line",
                        # Keep color contract identical to grid cells (band color).
                        "color": item.get("band_color") or "thermal-none",
                        "label": item.get("band_label") or "-",
                        "explanation": item.get("explanation") or "",
                    },
                ).model_dump()
            )
        return rows

    # Fallback when model criteria is unavailable.
    for item in score_items:
        if not isinstance(item, dict):
            continue
        key = item.get("criterion_key") or "Criterio"
        rows.append(
            DashboardComponent(
                type="score-row",
                properties={
                    "title": str(key).replace("_", " ").title(),
                    "score": float(item.get("score") or 0),
                    "max_score": 100.0,
                    "icon": item.get("band_icon") or "ri-star-line",
                    "color": item.get("band_color") or "thermal-none",
                    "label": item.get("band_label") or "-",
                    "explanation": item.get("explanation") or "",
                },
            ).model_dump()
        )
    return rows


def _build_v2_profile_header_props(
    lead: Dict[str, Any],
    intent_value: str,
    intent_icon: str,
    intent_color: str,
) -> Dict[str, Any]:
    score_total = float(lead.get("score_total") or 0)
    priority_label = lead.get("priority_label") or "Sin prioridad"
    priority_color = _resolve_priority_color(priority_label)

    return {
        "full_name": lead.get("full_name") or "Sin Nombre",
        "email": lead.get("email") or "Sin email",
        "phone": lead.get("phone") or "Sin teléfono",
        "reasoning": lead.get("reasoning") or "",
        "score_value": score_total,
        "score_color": priority_color or PALETTE_NEUTRAL,
        "intent_label": intent_value,
        "intent_color": intent_color,
        "intent_icon": intent_icon,
        "status_label": priority_label,
        "status_color": priority_color,
        "status_icon": "ri-speed-line",
    }

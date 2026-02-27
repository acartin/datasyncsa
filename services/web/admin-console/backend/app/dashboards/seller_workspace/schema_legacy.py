from app.contracts.ui_schema import UIComponent as DashboardComponent

from .schema import ClientUserDashboardSchema


def get_lead_detail_schema(user_id: str, lead_id: str, lead: dict) -> ClientUserDashboardSchema:
    """
    Returns the schema for the legacy Lead Detail view.
    """
    full_name = lead.get("full_name") or "Sin Nombre"
    email = lead.get("email") or "Sin email"
    phone = lead.get("phone") or "Sin teléfono"
    score_total = lead.get("score_total") or 0

    score_components = [
        DashboardComponent(
            type="score-row",
            properties={
                "title": "Interés",
                "score": lead.get("score_engagement") or 0,
                "max_score": 30,
                "icon": lead.get("eng_icon"),
                "color": lead.get("eng_color", "primary"),
                "label": lead.get("eng_label") or "-",
            },
        ),
        DashboardComponent(
            type="score-row",
            properties={
                "title": "Finanzas",
                "score": lead.get("score_finance") or 0,
                "max_score": 30,
                "icon": lead.get("fin_icon"),
                "color": lead.get("fin_color", "primary"),
                "label": lead.get("fin_label") or "-",
            },
        ),
        DashboardComponent(
            type="score-row",
            properties={
                "title": "Urgencia",
                "score": lead.get("score_timeline") or 0,
                "max_score": 30,
                "icon": lead.get("tim_icon"),
                "color": lead.get("tim_color", "primary"),
                "label": lead.get("tim_label") or "-",
            },
        ),
        DashboardComponent(
            type="score-row",
            properties={
                "title": "Match",
                "score": lead.get("score_match") or 0,
                "max_score": 30,
                "icon": lead.get("mat_icon"),
                "color": lead.get("mat_color", "primary"),
                "label": lead.get("mat_label") or "-",
            },
        ),
        DashboardComponent(
            type="score-row",
            properties={
                "title": "Calidad",
                "score": lead.get("score_info") or 0,
                "max_score": 30,
                "icon": lead.get("inf_icon"),
                "color": lead.get("inf_color", "primary"),
                "label": lead.get("inf_label") or "-",
            },
        ),
    ]

    contact_components = [
        DashboardComponent(
            type="info-row",
            properties={
                "label": "Teléfono",
                "value": lead.get("phone") or "-",
                "icon": "ri-phone-line",
                "color": "success",
            },
        ),
        DashboardComponent(
            type="info-row",
            properties={
                "label": "Email",
                "value": lead.get("email") or "-",
                "icon": "ri-mail-line",
                "color": "warning",
            },
        ),
        DashboardComponent(
            type="info-row",
            properties={
                "label": "Intención",
                "value": lead.get("cp_label") or "No definida",
                "icon": lead.get("cp_icon") or "ri-chat-1-line",
                "color": lead.get("cp_color", "primary"),
            },
        ),
        DashboardComponent(
            type="info-row",
            properties={
                "label": "Registrado",
                "value": lead.get("created_at").strftime("%d %b, %Y") if lead.get("created_at") else "-",
                "icon": "ri-calendar-line",
                "color": "info",
                "last": True,
            },
        ),
    ]

    return ClientUserDashboardSchema(
        layout="dashboard-standard",
        debug_data=lead,
        components=[
            DashboardComponent(
                type="back-link",
                properties={"text": "Volver", "fallback_url": "/leads/me"},
            ),
            DashboardComponent(
                type="profile-header",
                properties={
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "score_value": score_total,
                    "score_color": lead.get("prio_color"),
                    "intent_label": lead.get("cp_label"),
                    "intent_color": lead.get("cp_color", "primary"),
                    "intent_icon": lead.get("cp_icon"),
                    "status_label": lead.get("status_label"),
                    "status_color": lead.get("status_color", "warning"),
                    "status_icon": lead.get("status_icon"),
                },
            ),
            DashboardComponent(
                type="tabs",
                class_="border-0 shadow-none",
                items=[
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
                                            DashboardComponent(
                                                type="col",
                                                size=6,
                                                components=contact_components,
                                            ),
                                            DashboardComponent(
                                                type="col",
                                                size=6,
                                                components=score_components,
                                            ),
                                        ],
                                    )
                                ],
                            )
                        ],
                    },
                    {
                        "id": "tab-audit",
                        "label": "Audit",
                        "icon": "ri-file-list-3-line",
                        "content": [
                            DashboardComponent(
                                type="card",
                                components=[
                                    DashboardComponent(
                                        type="empty-state",
                                        properties={
                                            "title": "Historial de Cambios",
                                            "message": "El audit trail se mostrará aquí muy pronto.",
                                            "icon": "ri-history-line",
                                        },
                                    )
                                ],
                            )
                        ],
                    },
                    {
                        "id": "tab-source",
                        "label": "Fuente",
                        "icon": "ri-links-line",
                        "content": [
                            DashboardComponent(
                                type="card",
                                components=[
                                    DashboardComponent(
                                        type="empty-state",
                                        properties={
                                            "title": "Origen del Lead",
                                            "message": "Información detallada de la fuente se mostrará aquí.",
                                            "icon": "ri-links-line",
                                        },
                                    )
                                ],
                            )
                        ],
                    },
                ],
            ),
        ],
    )

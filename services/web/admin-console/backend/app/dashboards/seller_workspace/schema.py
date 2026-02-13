from typing import List, Optional
from pydantic import BaseModel
from app.contracts.ui_schema import UIComponent as DashboardComponent, WebIAFirstResponse


class ClientUserDashboardSchema(BaseModel):
    layout: str
    components: List[DashboardComponent]
    debug_data: Optional[dict] = None  # Added for debugging lead data in console


from app.modules.leads.router import LEADS_GRID_CONFIG_FULL

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

def get_lead_detail_schema(user_id: str, lead_id: str, lead: dict) -> ClientUserDashboardSchema:
    """
    Returns the Schema for the Lead Detail View (Drill-down).
    """
    # Extract lead data with defaults
    full_name = lead.get('full_name') or 'Sin Nombre'
    email = lead.get('email') or 'Sin email'
    phone = lead.get('phone') or 'Sin teléfono'
    score_total = lead.get('score_total') or 0
    status_label = lead.get('status_label') or 'Nuevo'
    status_color = lead.get('status_color') or 'warning'
    
    # Calculate gauge color based on score (Matching frontend formatters.js)
    gauge_color = '#475569'
    if score_total >= 90: gauge_color = '#f06548'
    elif score_total >= 70: gauge_color = '#f7b84b'
    elif score_total >= 50: gauge_color = '#4b38b3'
    elif score_total >= 20: gauge_color = '#0ab39c'
    
    # Get initials for avatar
    initials = ''.join([n[0].upper() for n in full_name.split()[:2]]) if full_name != 'Sin Nombre' else 'L'

    # Score Components using new Frontend Renderer
    score_components = [
        DashboardComponent(type="score-row", properties={
            "title": "Interés", "score": lead.get('score_engagement') or 0, "max_score": 30, 
            "icon": lead.get('eng_icon'), "color": lead.get('eng_color', 'primary'), "label": lead.get('eng_label') or '-'
        }),
        DashboardComponent(type="score-row", properties={
            "title": "Finanzas", "score": lead.get('score_finance') or 0, "max_score": 30, 
            "icon": lead.get('fin_icon'), "color": lead.get('fin_color', 'primary'), "label": lead.get('fin_label') or '-'
        }),
        DashboardComponent(type="score-row", properties={
            "title": "Urgencia", "score": lead.get('score_timeline') or 0, "max_score": 30, 
            "icon": lead.get('tim_icon'), "color": lead.get('tim_color', 'primary'), "label": lead.get('tim_label') or '-'
        }),
        DashboardComponent(type="score-row", properties={
            "title": "Match", "score": lead.get('score_match') or 0, "max_score": 30, 
            "icon": lead.get('mat_icon'), "color": lead.get('mat_color', 'primary'), "label": lead.get('mat_label') or '-'
        }),
        DashboardComponent(type="score-row", properties={
            "title": "Calidad", "score": lead.get('score_info') or 0, "max_score": 30, 
            "icon": lead.get('inf_icon'), "color": lead.get('inf_color', 'primary'), "label": lead.get('inf_label') or '-'
        })
    ]

    # Contact Info Components
    contact_components = [
        DashboardComponent(type="info-row", properties={
            "label": "Teléfono", "value": lead.get('phone') or '-', 
            "icon": "ri-phone-line", "color": "success"
        }),
        DashboardComponent(type="info-row", properties={
            "label": "Email", "value": lead.get('email') or '-',
            "icon": "ri-mail-line", "color": "warning"
        }),
        DashboardComponent(type="info-row", properties={
            "label": "Intención", "value": lead.get('cp_label') or 'No definida',
            "icon": lead.get('cp_icon') or "ri-chat-1-line", "color": lead.get('cp_color', 'primary')
        }),
        DashboardComponent(type="info-row", properties={
            "label": "Registrado", "value": lead.get('created_at').strftime('%d %b, %Y') if lead.get('created_at') else '-',
            "icon": "ri-calendar-line", "color": "info", "last": True
        })
    ]
    return ClientUserDashboardSchema(
        layout="dashboard-standard",
        debug_data=lead,
        components=[
            # Back to Dashboard
            DashboardComponent(
                type="back-link",
                properties={"text": "Volver", "fallback_url": "/leads/me"}
            ),
            # Banner Card (Profile Header)
            DashboardComponent(
                type="profile-header",
                properties={
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "score_value": score_total,
                    "score_color": lead.get('prio_color'),
                    "intent_label": lead.get('cp_label'),
                    "intent_color": lead.get('cp_color', 'primary'),
                    "intent_icon": lead.get('cp_icon'),
                    "status_label": lead.get('status_label'),
                    "status_color": lead.get('status_color', 'warning'),
                    "status_icon": lead.get('status_icon')
                }
            ),
            
            # Tabs (Información, Audit, Fuente)
            DashboardComponent(
                type="tabs",
                class_="border-0 shadow-none",
                items=[
                    {
                        "id": "tab-info", "label": "Información", "icon": "ri-information-line", "active": True,
                        "content": [
                            DashboardComponent(
                                type="card",
                                class_="border-0 shadow-none",
                                components=[
                                    DashboardComponent(
                                        type="row",
                                        class_="border-0",
                                        components=[
                                    # Column 1: Profile & Contact
                                    # Column 1: Profile & Contact
                                    DashboardComponent(
                                        type="col", size=6,
                                        components=contact_components
                                    ),
                                    # Column 2: Detailed Scoring (Redesigned Grid)
                                    DashboardComponent(
                                        type="col", size=6,
                                        components=score_components
                                    )
                                ]
                                    )
                                ]
                            )
                        ]
                    },
                    {
                        "id": "tab-audit", "label": "Audit", "icon": "ri-file-list-3-line",
                        "content": [
                            DashboardComponent(
                                type="card",
                                components=[
                                    DashboardComponent(
                                        type="empty-state",
                                        properties={
                                            "title": "Historial de Cambios",
                                            "message": "El audit trail se mostrará aquí muy pronto.",
                                            "icon": "ri-history-line"
                                        }
                                    )
                                ]
                            )
                        ]
                    },
                     {
                        "id": "tab-source", "label": "Fuente", "icon": "ri-links-line",
                        "content": [
                            DashboardComponent(
                                type="card",
                                components=[
                                    DashboardComponent(
                                        type="empty-state",
                                        properties={
                                            "title": "Origen del Lead",
                                            "message": "Información detallada de la fuente se mostrará aquí.",
                                            "icon": "ri-links-line"
                                        }
                                    )
                                ]
                            )
                        ]
                    }
                ]
            )
        ]
    )

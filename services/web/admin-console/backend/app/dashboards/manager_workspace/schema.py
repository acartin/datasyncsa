from typing import List
from pydantic import BaseModel
from app.contracts.ui_schema import UIComponent as DashboardComponent

class ManagerDashboardSchema(BaseModel):
    layout: str
    components: List[DashboardComponent]


from app.modules.leads.router import LEADS_GRID_CONFIG_FULL

def get_manager_workspace_schema(user_id: str) -> ManagerDashboardSchema:
    # 1. Configuración del Grid Personal (Importada de la Fuente de Verdad)
    grid_config = LEADS_GRID_CONFIG_FULL.copy() # Copia para evitar mutaciones
    # grid_id se mantiene como 'leads-me' para compartir Vistas Guardadas


    return ManagerDashboardSchema(
        layout="dashboard-standard",
        components=[
            DashboardComponent(
                type="tabs",
                # Tabs.js expects 'items' array at root
                items=[
                    {
                        "id": "tab-resumen", 
                        "label": "Resumen", 
                        "icon": "ri-dashboard-line",
                        "active": True,
                        "content": [
                            DashboardComponent(
                                type="row",
                                class_="row",
                                components=[
                                    DashboardComponent(
                                        type="col",
                                        class_="col-md-3",
                                        components=[
                                             DashboardComponent(
                                                type="card-metric",
                                                properties={
                                                    "title": "Leads Nuevos",
                                                    "value": "124",
                                                    "icon": "ri-user-add-line",
                                                    "trend": "+12%",
                                                    "color": "success"
                                                }
                                            )
                                        ]
                                    ),
                                    DashboardComponent(
                                        type="col",
                                        class_="col-md-3",
                                        components=[
                                             DashboardComponent(
                                                type="card-metric",
                                                properties={
                                                    "title": "Conversión",
                                                    "value": "8.5%",
                                                    "icon": "ri-pie-chart-line",
                                                    "trend": "+2.1%",
                                                    "color": "primary"
                                                }
                                            )
                                        ]
                                    ),
                                     DashboardComponent(
                                        type="col",
                                        class_="col-md-3",
                                        components=[
                                             DashboardComponent(
                                                type="card-metric",
                                                properties={
                                                    "title": "Interacciones AI",
                                                    "value": "1.2k",
                                                    "icon": "ri-robot-line",
                                                    "trend": "+15%",
                                                    "color": "info"
                                                }
                                            )
                                        ]
                                    ),
                                ]
                            ),
                             DashboardComponent(
                                type="row",
                                class_="row mt-4",
                                components=[
                                     DashboardComponent(
                                        type="col",
                                        class_="col-12",
                                        components=[
                                            DashboardComponent(
                                                type="card", 
                                                properties={"title": "Rendimiento de Equipo (Placeholder)"},
                                                components=[
                                                    DashboardComponent(
                                                        type="typography",
                                                        text="Gráfica de rendimiento próximamente...",
                                                        tag="p",
                                                        class_="text-muted"
                                                    )
                                                ]
                                            )
                                        ]
                                     )
                                ]
                            )
                        ]
                    },
                    {
                        "id": "tab-leads", 
                        "label": "Leads", 
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

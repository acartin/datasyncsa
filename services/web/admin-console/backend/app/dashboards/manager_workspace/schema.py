from typing import List
from pydantic import BaseModel
from app.contracts.ui_schema import UIComponent as DashboardComponent
from app.modules.shared.sdui import (
    create_modal_action,
    delete_action,
    edit_action,
    encode_schema_b64,
)

class ManagerDashboardSchema(BaseModel):
    layout: str
    components: List[DashboardComponent]

def _build_contacts_grid_properties() -> dict:
    create_schema_b64 = encode_schema_b64([
        {"name": "first_name", "label": "Nombre", "type": "text", "required": True},
        {"name": "last_name", "label": "Apellido", "type": "text", "required": False},
        {"name": "position", "label": "Cargo / Puesto", "type": "text", "required": False},
        {"name": "is_active", "label": "Activo", "type": "switch", "required": False},
        {
            "name": "channels",
            "label": "Canales de Comunicación",
            "type": "repeater",
            "source": "/contacts/categories",
        },
    ])
    convert_schema_b64 = encode_schema_b64([
        {"name": "email", "label": "Email de acceso", "type": "text", "required": True},
        {"name": "password", "label": "Contraseña inicial", "type": "password", "required": True},
    ])
    edit_schema_b64 = create_schema_b64

    return {
        "title": "Directorio de Contactos",
        "id": "contacts_grid_manager",
        "data_url": "/contacts/data",
        "auto_select_first_row": True,
        "columns": [
            {"id": "full_name", "label": "Nombre", "sortable": True},
            {"id": "position", "label": "Posición", "sortable": True},
            {
                "id": "is_active",
                "label": "Activo",
                "type": "badge",
                "badge_map": {"true": "success", "false": "secondary"},
            },
        ],
        "enableFilters": False,
        "filterConfig": {
            "searchFields": ["full_name", "position"],
            "filterableColumns": [
                {"id": "is_active", "label": "Activo", "icon": "ri-toggle-line"},
                {"id": "position", "label": "Posición", "icon": "ri-briefcase-4-line"},
            ],
        },
        "actions": [
            edit_action("/contacts/{id}", edit_schema_b64),
            {
                "label": "Convertir a Usuario",
                "icon": "ri-user-add-line",
                "action": "modal-form-create",
                "action_url": "/contacts/{id}/convert",
                "schema": convert_schema_b64,
                "modal_title": "Crear acceso para contacto",
                "prefill": {"email": "{primary_email}"},
                "color": "primary",
            },
            delete_action("/contacts/{id}"),
        ],
        "header_actions": [
            create_modal_action(
                action_url="/contacts",
                schema_b64=create_schema_b64,
                modal_title="Crear Contacto",
                label="Nuevo Contacto",
                icon="ri-user-add-line",
            )
        ],
    }


def _build_contacts_channels_feed_properties() -> dict:
    channel_schema_b64 = encode_schema_b64([
        {"name": "category_id", "label": "Categoría", "type": "select", "source": "/contacts/categories", "required": True},
        {"name": "type", "label": "Tipo de Canal", "type": "select", "source": "/contacts/channel-types", "required": True},
        {
            "name": "value",
            "label": "Valor",
            "type": "text",
            "required": True,
            "placeholder": "Ej: contacto@dominio.com",
            "placeholder_source": "type",
            "placeholder_map": {
                "email": "Ej: contacto@dominio.com",
                "phone": "Ej: 2222-3344",
                "mobile": "Ej: +506 8888-9999",
                "whatsapp": "Ej: +506 8888-9999",
                "telegram": "Ej: @usuario",
                "instagram": "Ej: @cuenta",
                "facebook": "Ej: facebook.com/pagina",
                "other": "Ingresa el dato de contacto",
            },
        },
        {"name": "label", "label": "Etiqueta", "type": "text", "required": False},
        {"name": "is_primary", "label": "Principal", "type": "switch", "required": False},
        {"name": "is_verified", "label": "Verificado", "type": "switch", "required": False},
    ])

    return {
        "title": "Canales de Comunicación",
        "id": "contacts_channels_feed_manager",
        "data_url": "/contacts/channels/data",
        "data_url_template": "/contacts/{master_id}/channels/data",
        "master_grid_id": "contacts_grid_manager",
        "master_row_field": "id",
        "master_url_token": "{master_id}",
        "empty_until_master": True,
        "columns": [
            {"id": "category_icon", "label": "", "type": "icon", "icon_only": True},
            {"id": "category_name", "label": "Canal", "sortable": True},
            {"id": "value", "label": "Detalle", "sortable": True},
            {"id": "is_primary", "label": "Principal", "type": "badge", "badge_map": {"true": "success", "false": "secondary"}},
            {"id": "is_verified", "label": "Verificado", "type": "badge", "badge_map": {"true": "info", "false": "secondary"}},
        ],
        "enableFilters": False,
        "filterConfig": {
            "searchFields": ["category_name", "type", "value", "label"],
        },
        "actions": [
            edit_action("/contacts/{contact_id}/channels/{id}", channel_schema_b64),
            delete_action("/contacts/{contact_id}/channels/{id}"),
        ],
        "header_actions": [
            {
                "label": "Nuevo Canal",
                "icon": "ri-add-line",
                "action": "modal-form-create",
                "action_url": "/contacts/{master_id}/channels",
                "schema": channel_schema_b64,
                "modal_title": "Agregar canal",
                "color": "success",
                "requires_master": True,
                "show_disabled_when_locked": True,
                "locked_label": "Seleccione contacto",
            }
        ],
    }


def get_manager_workspace_schema(user_id: str, leads_grid_config: dict) -> ManagerDashboardSchema:
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
                                properties=leads_grid_config
                            )
                        ]
                    },
                    {
                        "id": "tab-contacts",
                        "label": "Contactos",
                        "icon": "ri-contacts-book-2-line",
                        "content": [
                            DashboardComponent(
                                type="row",
                                class_="g-4",
                                components=[
                                    DashboardComponent(
                                        type="col",
                                        class_="col-12 col-xl-7",
                                        components=[
                                            DashboardComponent(
                                                type="grid-visual",
                                                label="Directorio de Contactos",
                                                properties=_build_contacts_grid_properties(),
                                            )
                                        ],
                                    ),
                                    DashboardComponent(
                                        type="col",
                                        class_="col-12 col-xl-5",
                                        components=[
                                            DashboardComponent(
                                                type="grid-visual",
                                                label="Todos los Canales",
                                                properties=_build_contacts_channels_feed_properties(),
                                            )
                                        ],
                                    ),
                                ],
                            )
                        ],
                    }
                ]
            )
        ]
    )

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from app.contracts.ui_schema import WebIAFirstResponse
from .schemas import ClientCreate, ClientUpdate, ClientRow, ClientSimple
from .service import service
from typing import List
from app.modules.auth.dependencies import RoleChecker
from uuid import UUID
import json
import base64
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User as AuthUser
from fastapi import UploadFile, File, Form
from typing import Optional
import logging
from sqlalchemy import text
from app.dal.database import engine

# Security: Admin, System User and Client Admin can access
router = APIRouter(dependencies=[Depends(RoleChecker(["admin", "system-user", "client-admin"]))])
logger = logging.getLogger(__name__)

CLIENT_FORM_FIELDS = [
    {"name": "name", "label": "Nombre del Cliente", "type": "text", "required": True, "min_length": 2},
    {
        "name": "country_id",
        "label": "País",
        "type": "select",
        "source": "/countries/data",
        "required": True,
    },
    {
        "name": "vertical_id",
        "label": "Vertical",
        "type": "select",
        "source": "/clients/verticals/options",
        "required": True,
    },
    {
        "name": "scoring_model_id",
        "label": "Modelo de Scoring",
        "type": "select",
        "source": "/clients/scoring-models/options?vertical_id={vertical_id}",
        "required": False,
        "depends_on": "vertical_id",
    },
]

# --- SERVER DRIVEN UI (SDUI) ---

@router.get("/clients", response_model=WebIAFirstResponse)
async def get_clients_view(current_user: AuthUser = Depends(current_active_user)):
    """
    Returns the UI structure for the Clients Module.
    - Admin: Returns Grid (List of Clients).
    - Client Admin: Returns Dashboard (Tabs) for their specific Client.
    """
    
    # 1. Super Admin Logic (Show Grid)
    if current_user.is_superuser:
        return {
            "layout": "dashboard-standard",
            "components": [
                {
                    "type": "grid-visual",
                    "label": "Gestión de Clientes",
                    "properties": {
                        "data_url": "/clients/data",
                        "primary_key": "id",
                        "columns": [
                            {"id": "name", "label": "Nombre del Cliente", "type": "text", "sortable": True},
                            {"id": "country_name", "label": "País", "type": "text", "sortable": True},
                            {"id": "vertical_name", "label": "Vertical", "type": "text", "sortable": True},
                            {"id": "scoring_model_name", "label": "Modelo", "type": "text", "sortable": True},
                            {"id": "id", "label": "ID", "type": "text", "sortable": True, "hidden": True}
                        ],
                        "enableFilters": True,
                        "filterConfig": {
                            "searchFields": ["name", "country_name"],
                            "filterableColumns": [
                                {"id": "country_name", "label": "País", "icon": "ri-earth-line"},
                                {"id": "vertical_name", "label": "Vertical", "icon": "ri-stack-line"}
                            ]
                        },
                        "form_schema": [
                            *CLIENT_FORM_FIELDS
                        ],
                        "actions": [
                            {
                                "type": "button",
                                "icon": "ri-edit-line",
                                "label": "Editar",
                                "action": "modal-form",
                                "action_url": "/clients/{id}", 
                                "modal_title": "Editar Cliente"
                            },
                            {
                                "type": "button",
                                "icon": "ri-delete-bin-line",
                                "label": "Eliminar",
                                "color": "danger",
                                "action": "api-call",
                                "method": "DELETE",
                                "action_url": "/clients/{id}",
                                "confirm_message": "¿Estás seguro de eliminar este cliente?"
                            },
                            {
                                "type": "button",
                                "icon": "ri-dashboard-line",
                                "label": "Gestionar",
                                "color": "info",
                                "action": "navigate",
                                "action_url": "/clients/{id}/dashboard"
                            }
                        ],
                        "header_actions": [
                            {
                                "type": "button",
                                "icon": "ri-add-line",
                                "label": "Nuevo Cliente",
                                "color": "success",
                                "action": "modal-form",
                                "action_url": "/clients",
                                "modal_title": "Nuevo Cliente",
                                "schema": CLIENT_FORM_FIELDS
                            }
                        ]
                    }
                }
            ],
            "permissions_required": ["clients.view"]
        }

    # 2. Client Admin Logic (Show Dashboard directly)
    if current_user.tenants:
        # Assuming single tenant context for now
        client_id = current_user.tenants[0].client_id
        return await get_client_dashboard(client_id, current_user)

    # 3. Fallback (No tenant, not admin)
    raise HTTPException(status_code=403, detail="No client context assigned.")

# --- DATA API (CRUD) ---

@router.get("/clients/data", response_model=List[ClientRow])
async def list_clients_data():
    """Returns raw data for the Grid."""
    return await service.list_clients()

@router.get("/clients/simple-list", response_model=List[ClientSimple])
async def list_simple_clients():
    """Returns a simple ID/Name list for dropdowns."""
    return await service.list_simple()

@router.get("/clients/scoring-models/options")
async def list_scoring_models_options(vertical_id: Optional[int] = Query(None)):
    """Returns scoring model options filtered by vertical."""
    return await service.list_scoring_model_options(vertical_id)

@router.get("/clients/verticals/options")
async def list_verticals_options():
    """Returns vertical options for clients CRUD."""
    return await service.list_vertical_options()

@router.post("/clients", response_model=ClientRow)
async def create_client(client: ClientCreate):
    return await service.create_client(client)

@router.get("/clients/{client_id}", response_model=ClientRow)
async def get_client(client_id: UUID):
    """Used for populating Edit Modals"""
    item = await service.get_client(client_id)
    if not item:
        raise HTTPException(status_code=404, detail="Client not found")
    return item

@router.put("/clients/{client_id}", response_model=ClientRow)
async def update_client(client_id: UUID, client: ClientUpdate):
    item = await service.update_client(client_id, client)
    if not item:
        raise HTTPException(status_code=404, detail="Client not found")
    return item

@router.delete("/clients/{client_id}")
async def delete_client(client_id: UUID):
    success = await service.delete_client(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"status": "deleted"}

@router.get("/clients/{client_id}/dashboard", response_model=WebIAFirstResponse)
async def get_client_dashboard(client_id: UUID, current_user: AuthUser = Depends(current_active_user)):
    """
    Returns the Tabs View for a specific Client.
    """
    client = await service.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Define Tabs
    tabs = []

    # 1. Overview (Everyone)
    tabs.append({
        "id": "overview",
        "label": "Resumen",
        "icon": "ri-pie-chart-line",
        "active": True,
        "content": [
                {"type": "typography", "variant": "p", "content": "Métricas generales próximamente."}
        ]
    })

    # 2. Contacts (Everyone authenticated for this client)
    # Note: Actions for contacts are already secured by backend, but we could hide "Create" button here if needed.
    tabs.append({
        "id": "contacts",
        "label": "Contactos",
        "icon": "ri-contacts-book-line",
        "content": [
            {
                "type": "grid-visual",
                "label": "Directorio de Contactos",
                "properties": {
                    "data_url": f"/contacts/data?client_id={client_id}",
                    "primary_key": "id",
                    "columns": [
                        {"id": "first_name", "label": "Nombre", "type": "text", "sortable": True},
                        {"id": "last_name", "label": "Apellido", "type": "text", "sortable": True},
                        {"id": "position", "label": "Posición", "type": "text"},
                        {"id": "is_active", "label": "Estado", "type": "badge", "badge_map": {"True": "success", "False": "danger"}}
                    ],
                    "header_actions": [
                        {
                            "type": "button",
                            "icon": "ri-user-add-line",
                            "label": "Nuevo Contacto",
                            "color": "primary",
                            "action": "modal-form",
                            "action_url": "/contacts",
                            "method": "POST",
                            "modal_title": "Crear Contacto",
                            "schema": [
                                {"name": "first_name", "label": "Nombre", "type": "text", "required": True},
                                {"name": "last_name", "label": "Apellido", "type": "text", "required": True},
                                {"name": "position", "label": "Cargo / Puesto", "type": "text"},
                                {"name": "is_active", "label": "Estado Activo", "type": "switch", "value": True},
                                {"name": "channels", "label": "Canales de Comunicación", "type": "repeater", "source": "/contacts/categories"},
                                {"name": "client_id", "type": "hidden", "value": str(client_id)}
                            ]
                        }
                    ],
                    "actions": [
                        {
                            "type": "button",
                            "icon": "ri-edit-line",
                            "label": "Editar",
                            "action": "modal-form",
                            "action_url": "/contacts/{id}",
                            "modal_title": "Editar Contacto",
                            "schema": [
                                {"name": "first_name", "label": "Nombre", "type": "text", "required": True},
                                {"name": "last_name", "label": "Apellido", "type": "text", "required": True},
                                {"name": "position", "label": "Cargo / Puesto", "type": "text"},
                                {"name": "is_active", "label": "Estado Activo", "type": "switch"},
                                {"name": "channels", "label": "Canales de Comunicación", "type": "repeater", "source": "/contacts/categories"}
                            ]
                        },
                        {
                            "type": "button",
                            "icon": "ri-delete-bin-line",
                            "label": "Eliminar",
                            "color": "danger",
                            "action": "delete",
                            "action_url": "/contacts/{id}",
                            "confirm_message": "¿Estás seguro de que deseas eliminar este contacto?"
                        }
                    ]
                }
            }
        ]
    })

    prompt_form_schema = [
        {"name": "client_id", "type": "hidden", "value": str(client_id)},
        {
            "name": "slug",
            "label": "Slug / Nombre Unico",
            "type": "text",
            "required": True,
            "min_length": 3,
            "placeholder": "ej. primary_chat",
        },
        {
            "name": "prompt_text",
            "label": "Instrucciones del Prompt",
            "type": "textarea",
            "required": True,
            "min_length": 10,
            "rows": 20,
        },
        {
            "name": "is_active",
            "label": "Activo",
            "type": "switch",
            "value": True,
        },
    ]

    # 3. Prompts (CRUD scoped to current client)
    tabs.append({
        "id": "prompts",
        "label": "Prompts",
        "icon": "ri-robot-line",
        "content": [
            {
                "type": "grid-visual",
                "label": "Prompts del Cliente",
                "properties": {
                    "data_url": f"/prompts/data?client_id={client_id}",
                    "primary_key": "id",
                    "columns": [
                        {"id": "slug", "label": "Slug", "type": "text", "sortable": True},
                        {"id": "prompt_text", "label": "Contenido", "type": "text", "truncate": 100},
                        {"id": "is_active", "label": "Activo", "type": "badge", "badge_map": {"true": "success", "false": "secondary"}},
                        {"id": "updated_at", "label": "Actualizado", "type": "datetime", "sortable": True},
                    ],
                    "enableFilters": True,
                    "filterConfig": {
                        "searchFields": ["slug", "prompt_text"]
                    },
                    "header_actions": [
                        {
                            "type": "button",
                            "icon": "ri-add-line",
                            "label": "Nuevo Prompt",
                            "color": "success",
                            "action": "modal-form",
                            "action_url": "/prompts",
                            "modal_title": "Crear Prompt",
                            "schema": prompt_form_schema,
                        }
                    ],
                    "actions": [
                        {
                            "type": "button",
                            "icon": "ri-edit-line",
                            "label": "Editar",
                            "action": "modal-form",
                            "action_url": "/prompts/{id}",
                            "modal_title": "Editar Prompt",
                            "schema": prompt_form_schema,
                        },
                        {
                            "type": "button",
                            "icon": "ri-delete-bin-line",
                            "label": "Eliminar",
                            "color": "danger",
                            "action": "delete",
                            "action_url": "/prompts/{id}",
                            "confirm_message": "¿Estás seguro de eliminar este prompt?",
                        }
                    ]
                }
            }
        ]
    })

    # 4. Branding (Superuser ONLY)
    if current_user.is_superuser:
        tabs.append({
            "id": "branding",
            "label": "Branding",
            "icon": "ri-palette-line",
            "content": [
                {
                     "type": "grid-visual",
                     "label": "Configuración de Marcas (Branding)",
                     "properties": {
                         "title": "Proyectos y Marcas",
                         "id": "branding_grid",
                         "primary_key": "project",
                         "data_url": f"/brand-config/{client.id}/list",
                         "enableFilters": True,
                         "filterConfig": {
                             "searchPlaceholder": "Buscar por proyecto, color o fuente...",
                             "searchFields": ["project", "primary_color", "font_heading_name", "font_body_name"]
                         },
                         "columns": [
                             {"id": "project", "label": "Proyecto"},
                             {"id": "primary_color", "label": "Primario", "type": "color"},
                             {"id": "secondary_color", "label": "Secundario", "type": "color"},
                             {"id": "surface_color", "label": "Superficie", "type": "color"}
                         ],
                         "actions": [
                             {
                                 "type": "button",
                                 "label": "Editar",
                                 "icon": "ri-edit-line",
                                 "action": "modal-form",
                                 "action_url": f"/brand-config/{client.id}/item?project={{project}}",
                                 "modal_title": "Editar Configuración de Marca",
                                 "schema": BRAND_FORM_SCHEMA_B64
                             },
                             {
                                 "type": "button",
                                 "icon": "ri-delete-bin-line",
                                 "label": "Eliminar",
                                 "color": "danger",
                                 "action": "delete",
                                 "action_url": f"/brand-config/{client.id}?project={{project}}",
                                 "confirm_message": "¿Estás seguro de que deseas eliminar esta configuración de marca?"
                             }
                         ],
                         "header_actions": [
                             {
                                 "type": "button",
                                 "label": "Nueva Configuración",
                                 "icon": "ri-add-line",
                                 "color": "success",
                                 "action": "modal-form",
                                 "action_url": f"/brand-config/{client.id}",
                                 "modal_title": "Nueva Configuración de Marca",
                                 "schema": BRAND_FORM_SCHEMA_B64
                             }
                         ]
                     }
                }
            ]
        })

    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "typography",
                "variant": "h4",
                "content": f"Cliente: {client.name} <span class='badge bg-success ms-2'>Active</span>",
                "class": "mb-4"
            },
            {
                "type": "tabs",
                "items": tabs
            }
        ],
        "permissions_required": ["clients.view"]
    }

# --- BRAND CONFIG ---

# Schema definition for Modal (Base64) - Moved here for reuse
BRAND_FORM_FIELDS = [
    {"name": "project", "label": "Nombre del Proyecto", "type": "text", "required": True, "value": "default", "readonly": True},
    {
        "type": "group",
        "label": "Colores del Tema",
        "layout": "horizontal",
        "fields": [
            {"name": "primary_color", "label": "Primario", "type": "color", "required": True, "value": "#000000"},
            {"name": "secondary_color", "label": "Secundario", "type": "color", "required": False, "value": "#333333"},
            {"name": "surface_color", "label": "Superficie", "type": "color", "required": False, "value": "#F5F5F5"}
        ]
    },
    {"name": "font_heading_name", "label": "Fuente Títulos", "type": "select", "options": [{"label": "Inter", "value": "Inter"}, {"label": "Roboto", "value": "Roboto"}, {"label": "Open Sans", "value": "Open Sans"}, {"label": "Montserrat", "value": "Montserrat"}, {"label": "Playfair Display", "value": "Playfair Display"}], "required": True, "value": "Inter"},
    {"name": "font_body_name", "label": "Fuente Cuerpo", "type": "select", "options": [{"label": "Inter", "value": "Inter"}, {"label": "Roboto", "value": "Roboto"}, {"label": "Open Sans", "value": "Open Sans"}, {"label": "Lato", "value": "Lato"}], "required": True, "value": "Inter"},
    {"name": "border_radius", "label": "Radio de Borde", "type": "select", "options": [{"label": "Pequeño (2px)", "value": "2px"}, {"label": "Medio (4px)", "value": "4px"}, {"label": "Redondo (8px)", "value": "8px"}, {"label": "Full (99px)", "value": "99px"}], "required": False, "value": "4px"},
    {"name": "box_shadow_style", "label": "Sombra (Estilo)", "type": "select", "options": [{"label": "Ninguna", "value": "none"}, {"label": "Sutil", "value": "0 4px 6px -1px rgb(0 0 0 / 0.1)"}, {"label": "Elevada", "value": "0 10px 15px -3px rgb(0 0 0 / 0.1)"}], "required": False, "value": "none"},
    {"name": "logo_header", "label": "Logo Header", "type": "file", "accept": "image/*", "required": False},
    {"name": "logo_square", "label": "Logo Cuadrado", "type": "file", "accept": "image/*", "required": False},
    {"name": "banner_main", "label": "Banner Principal", "type": "file", "accept": "image/*", "required": False},
    {"name": "banner_promo", "label": "Banner Promocional", "type": "file", "accept": "image/*", "required": False}
]
BRAND_FORM_SCHEMA_B64 = base64.b64encode(json.dumps(BRAND_FORM_FIELDS).encode()).decode()

FONT_URL_MAP = {
    "Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap",
    "Roboto": "https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap",
    "Open Sans": "https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap",
    "Montserrat": "https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap",
    "Playfair Display": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&display=swap",
    "Lato": "https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&display=swap",
}


def _row_to_brand_dict(row) -> dict:
    data = dict(row._mapping)
    # Keep compatibility with existing form field names
    if data.get("logo_header_path"):
        data["logo_header"] = data["logo_header_path"]
    if data.get("logo_square_path"):
        data["logo_square"] = data["logo_square_path"]
    if data.get("banner_main_path"):
        data["banner_main"] = data["banner_main_path"]
    if data.get("banner_promo_path"):
        data["banner_promo"] = data["banner_promo_path"]
    return data


@router.get("/brand-config/{client_id}/list")
async def list_brand_configs(client_id: UUID, current_user: AuthUser = Depends(current_active_user)):
    query = text(
        """
        SELECT
            client_id, project, primary_color, secondary_color, surface_color,
            font_heading_url, font_heading_name, font_body_url, font_body_name,
            border_radius, box_shadow_style,
            logo_header_path, logo_square_path, banner_main_path, banner_promo_path,
            updated_at
        FROM lead_brand_configs
        WHERE client_id = :client_id
        ORDER BY project
        """
    )
    async with engine.connect() as conn:
        rows = (await conn.execute(query, {"client_id": str(client_id)})).fetchall()
    return [_row_to_brand_dict(row) for row in rows]

@router.get("/brand-config/{client_id}/item")
async def get_brand_config_item(
    client_id: UUID,
    project: str = Query("default"),
    current_user: AuthUser = Depends(current_active_user)
):
    """Get a specific brand configuration by project name"""
    query = text(
        """
        SELECT
            client_id, project, primary_color, secondary_color, surface_color,
            font_heading_url, font_heading_name, font_body_url, font_body_name,
            border_radius, box_shadow_style,
            logo_header_path, logo_square_path, banner_main_path, banner_promo_path,
            updated_at
        FROM lead_brand_configs
        WHERE client_id = :client_id AND project = :project
        LIMIT 1
        """
    )
    async with engine.connect() as conn:
        row = (await conn.execute(query, {"client_id": str(client_id), "project": project})).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Brand configuration not found")
    return _row_to_brand_dict(row)



@router.delete("/brand-config/{client_id}")
async def delete_brand_config(
    client_id: UUID,
    project: str = Query("default"),
    current_user: AuthUser = Depends(current_active_user)
):
    """Delete a specific brand configuration"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only admins can delete branding")
    
    delete_q = text(
        """
        DELETE FROM lead_brand_configs
        WHERE client_id = :client_id AND project = :project
        """
    )
    async with engine.begin() as conn:
        result = await conn.execute(delete_q, {"client_id": str(client_id), "project": project})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Brand configuration not found")
    return {"status": "success", "message": f"Brand configuration '{project}' deleted"}

@router.post("/brand-config/{client_id}")
@router.put("/brand-config/{client_id}/item")  # Support PUT for edit action
async def proxy_update_brand_config(
    client_id: UUID,
    project: str = Form("default"),
    primary_color: str = Form(...),
    secondary_color: str = Form(None),
    surface_color: str = Form(None),
    font_heading_name: str = Form(...),
    font_body_name: str = Form(...),
    border_radius: str = Form(...),
    box_shadow_style: str = Form(None),
    logo_header: Optional[UploadFile] = File(None),
    logo_square: Optional[UploadFile] = File(None),
    banner_main: Optional[UploadFile] = File(None),
    banner_promo: Optional[UploadFile] = File(None),
    current_user: AuthUser = Depends(current_active_user)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only admins can configure branding")

    logo_header_base64 = None
    logo_header_path = None
    if logo_header and logo_header.filename:
        content = await logo_header.read()
        if content:
            logo_header_base64 = base64.b64encode(content).decode()
            logo_header_path = logo_header.filename

    logo_square_base64 = None
    logo_square_path = None
    if logo_square and logo_square.filename:
        content = await logo_square.read()
        if content:
            logo_square_base64 = base64.b64encode(content).decode()
            logo_square_path = logo_square.filename

    banner_main_path = banner_main.filename if banner_main and banner_main.filename else None
    banner_promo_path = banner_promo.filename if banner_promo and banner_promo.filename else None

    upsert_q = text(
        """
        INSERT INTO lead_brand_configs (
            id, client_id, project, primary_color, secondary_color, surface_color,
            font_heading_name, font_heading_url, font_body_name, font_body_url,
            border_radius, box_shadow_style,
            logo_header_base64, logo_square_base64, logo_header_path, logo_square_path,
            banner_main_path, banner_promo_path, updated_at
        ) VALUES (
            gen_random_uuid(), :client_id, :project, :primary_color, :secondary_color, :surface_color,
            :font_heading_name, :font_heading_url, :font_body_name, :font_body_url,
            :border_radius, :box_shadow_style,
            :logo_header_base64, :logo_square_base64, :logo_header_path, :logo_square_path,
            :banner_main_path, :banner_promo_path, now()
        )
        ON CONFLICT (client_id, project) DO UPDATE SET
            primary_color = EXCLUDED.primary_color,
            secondary_color = EXCLUDED.secondary_color,
            surface_color = EXCLUDED.surface_color,
            font_heading_name = EXCLUDED.font_heading_name,
            font_heading_url = EXCLUDED.font_heading_url,
            font_body_name = EXCLUDED.font_body_name,
            font_body_url = EXCLUDED.font_body_url,
            border_radius = EXCLUDED.border_radius,
            box_shadow_style = EXCLUDED.box_shadow_style,
            logo_header_base64 = COALESCE(EXCLUDED.logo_header_base64, lead_brand_configs.logo_header_base64),
            logo_square_base64 = COALESCE(EXCLUDED.logo_square_base64, lead_brand_configs.logo_square_base64),
            logo_header_path = COALESCE(EXCLUDED.logo_header_path, lead_brand_configs.logo_header_path),
            logo_square_path = COALESCE(EXCLUDED.logo_square_path, lead_brand_configs.logo_square_path),
            banner_main_path = COALESCE(EXCLUDED.banner_main_path, lead_brand_configs.banner_main_path),
            banner_promo_path = COALESCE(EXCLUDED.banner_promo_path, lead_brand_configs.banner_promo_path),
            updated_at = now()
        """
    )
    payload = {
        "client_id": str(client_id),
        "project": project or "default",
        "primary_color": primary_color,
        "secondary_color": secondary_color,
        "surface_color": surface_color,
        "font_heading_name": font_heading_name,
        "font_heading_url": FONT_URL_MAP.get(font_heading_name, ""),
        "font_body_name": font_body_name,
        "font_body_url": FONT_URL_MAP.get(font_body_name, ""),
        "border_radius": border_radius,
        "box_shadow_style": box_shadow_style,
        "logo_header_base64": logo_header_base64,
        "logo_square_base64": logo_square_base64,
        "logo_header_path": logo_header_path,
        "logo_square_path": logo_square_path,
        "banner_main_path": banner_main_path,
        "banner_promo_path": banner_promo_path,
    }

    async with engine.begin() as conn:
        await conn.execute(upsert_q, payload)

    return {"status": "success", "message": f"Brand configuration for '{project}' updated"}

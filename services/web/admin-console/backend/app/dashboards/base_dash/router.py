from fastapi import APIRouter, Depends
from app.contracts.ui_schema import WebIAFirstResponse, UIAppShell
from .menus import get_menu_for_role
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User
from app.modules.auth.utils import get_current_role_slug

router = APIRouter()

@router.get("/app-init", response_model=UIAppShell)
async def app_init(user: User = Depends(current_active_user)):
    """
    Returns the initial application shell structure.
    In the decentralized model, this provides the global shell.
    Navigation to specific dashboards is handled by menu links.
    """
    current_role = get_current_role_slug(user)
    
    # 2. Get Menu
    menu_items = get_menu_for_role(current_role)
    
    # 3. Get Initial Content based on Role
    initial_content = []
    
    # Role-based landing logic
    if current_role == "client-admin" and user.tenants:
        # Legacy import removed

        # We try to get the dashboard content. Since it's a route, we call the logic.
        # Note: This is a bit recursive in dependencies, better to import the builder.
        # For now, let's just use the bienvenida or a redirect hint.
        # Actually, let's keep it simple: just show a tailored bienvenida.
        initial_content = [
            {
                "type": "grid",
                "components": [
                    {"type": "typography", "tag": "h2", "text": f"Panel de Control: {user.name or 'Admin'}", "class": "mb-4"},
                    {"type": "card-metric", "label": "Rol Administrativo", "value": "SUPERVISOR", "color": "primary"}
                ]
            }
        ]
    elif current_role == "client-user":
        initial_content = [
            {
                "type": "grid",
                "components": [
                    {"type": "typography", "tag": "h2", "text": f"Panel Operativo: {user.name or 'Vendedor'}", "class": "mb-4"},
                    {"type": "card-metric", "label": "Rol Vendedor", "value": "EJECUTIVO", "color": "success"}
                ]
            }
        ]
    else:
        initial_content = [
            {
                "type": "grid",
                "components": [
                    {"type": "typography", "tag": "h2", "text": f"Bienvenido, {user.name or 'Usuario'}", "class": "mb-4"},
                    {"type": "card-metric", "label": "Tu Rol Actual", "value": current_role.upper(), "color": "info"}
                ]
            }
        ]
    
    return {
        "layout": "dashboard-shell",
        "sidebar": {
            "brand": "AI First",
            "items": menu_items
        },
        "content": initial_content
    }

@router.get("/base", response_model=WebIAFirstResponse)
async def get_base_dashboard(user: User = Depends(current_active_user)):
    """
    The standard Landing Dashboard for the system.
    """
    current_role = get_current_role_slug(user)
    
    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "grid",
                "components": [
                    {"type": "typography", "tag": "h2", "text": "Dashboard General", "class": "mb-4"},
                    {"type": "card-metric", "label": "Resumen de Actividad", "value": "Sincronizado", "color": "success"},
                    {"type": "typography", "tag": "p", "text": f"Estás visualizando el dashboard base con el rol {current_role}.", "color": "muted"}
                ]
            }
        ],
        "permissions_required": ["dashboard.view"]
    }

@router.get("/check-contract", response_model=WebIAFirstResponse)
async def validate_ia_guard():
    # Respuesta enriquecida para validación visual de Tema Velzon
    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "grid",
                "components": [
                    {"type": "typography", "tag": "h2", "text": "Tema Velzon Activo", "class": "mb-3"},
                    {"type": "typography", "tag": "p", "text": "Esta es una prueba de tipografía Inter con los colores del tema.", "color": "muted"},
                    
                    {"type": "button-group", "buttons": [
                        {"label": "Primary Action", "variant": "primary"},
                        {"label": "Success", "variant": "success"},
                        {"label": "Danger Zone", "variant": "danger"}
                    ]},

                    {"type": "card-metric", "label": "Validación Exitosa", "color": "success"},
                ]
            }
        ],
        "permissions_required": ["system.view"]
    }

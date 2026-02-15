from typing import List, Dict

# 1. Definimos los bloques (LEGOs)
MENU_DASHBOARD = {"id": "dash", "label": "Dashboard", "icon": "ri-dashboard-2-line", "link": "/base"}
MENU_CLIENTS   = {"id": "clients", "label": "Admin Clientes", "icon": "ri-building-line", "link": "/clients"}
MENU_PROMPTS   = {"id": "prompts", "label": "AI Prompts", "icon": "ri-robot-line", "link": "/prompts"}
MENU_COUNTRIES   = {"id": "items", "label": "Paises", "icon": "ri-map-pin-line", "link": "/countries"}

MENU_AI_LIBRARY = {"id": "ai-library", "label": "Biblioteca de IA", "icon": "ri-book-line", "link": "/ai-library"}

# NUEVO: Mission Control (Unifica Admin + Dashboard Personal)

MENU_MISSION_CONTROL = {"id": "mission-control", "label": "Home", "icon": "ri-home-4-line", "link": "/dashboard/manager"}

# Dashboard solo para vendedores (Seller Workspace)
MENU_SELLER_WORKSPACE = {"id": "seller-workspace", "label": "Mi Dashboard", "icon": "ri-dashboard-line", "link": "/dashboard/seller"}

# Submenú Sistema
MENU_SYSTEM = {
    "id": "sys", 
    "label": "Sistema", 
    "icon": "ri-settings-line", 
    "subItems": [
        {"id": "users", "label": "Usuarios", "link": "/system/users"},
        {"id": "roles", "label": "Roles", "link": "/system/roles"},
        {"id": "public-docs", "label": "Documentos Públicos", "link": "/system/public-docs"},
        {"id": "countries", "label": "Países (Global)", "link": "/countries"}
    ]
}

# Fallback por seguridad (si el rol no existe o es null)
DEFAULT_MENU = [MENU_DASHBOARD]

# --- NUEVOS ROLES DE PRUEBA ---
ROLE_MENUS = {
    # 1. Super Admin (TÚ)
    "admin": [
        MENU_DASHBOARD,
        MENU_CLIENTS,    # Gestión de Inquilinos
        MENU_PROMPTS,
        MENU_SYSTEM
    ],

    # 2. System User (Datasync)
    # Rol técnico interno, ve estado del sistema pero no clientes
    "system-user": [
        MENU_DASHBOARD,
        {"id": "sys-status", "label": "Estado Servidores", "icon": "ri-server-line", "link": "/status"},
        {"id": "logs", "label": "Audit Logs", "icon": "ri-file-list-3-line", "link": "/logs"},
        MENU_SYSTEM
    ],
    
    # 3. Client Admin (Coca Cola Boss)
    # Ve "Mission Control" (Visión panorámica + personal) y su gestión
    "client-admin": [
        MENU_MISSION_CONTROL, # <--- CAMBIO: Unificado
        # MENU_SELLER_WORKSPACE eliminado para no duplicar. Su data vive en Mission Control.
        {"id": "leads-me", "label": "Mis Leads", "icon": "ri-user-star-line", "link": "/leads/me"}, # INTOCABLE
        {"id": "campaigns", "label": "Campañas", "icon": "ri-megaphone-line", "link": "/campaigns"},
        MENU_AI_LIBRARY
    ],
    
    # 4. Client User (Coca Cola Vendedor)
    # Operativo puro
    "client-user": [
        MENU_SELLER_WORKSPACE,
        {"id": "leads-me", "label": "Mis Leads", "icon": "ri-user-star-line", "link": "/leads/me"},
        {"id": "tasks", "label": "Mis Tareas", "icon": "ri-task-line", "link": "/tasks"}
    ]
}

def get_menu_for_role(role_slug: str) -> List[Dict]:
    """Retorna la lista de menús permitidos para un rol."""
    return ROLE_MENUS.get(role_slug, DEFAULT_MENU)

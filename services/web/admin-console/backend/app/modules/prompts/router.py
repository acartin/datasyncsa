from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import UUID

from .schemas import PromptCreate, PromptUpdate, PromptRow
from .service import service
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User
from app.modules.auth.dependencies import RoleChecker
from app.modules.shared.sdui import create_modal_action, delete_action, encode_schema_b64

# Enforcing RBAC: Only Super Admins and Client Admins can manage Prompts
# Client Users (Sales) can only consume them (via different endpoints if needed, or backend logic)
# Here we restrict the MANAGEMENT interface.
router = APIRouter(
    prefix="/prompts",
    tags=["AI Prompts"],
    dependencies=[Depends(RoleChecker(["admin", "system-user", "client-admin"]))]
)

# --- Helper: Context Extraction ---
def get_current_client_id(user: User) -> UUID:
    """
    Extracts the active Client ID for the current user.
    For MVP, we default to the first tenant found.
    Future: Read from 'X-Client-ID' header and validate against user.tenants.
    """
    if not user.tenants:
        raise HTTPException(status_code=403, detail="User is not assigned to any client tenant.")
    
    # Return the ID of the first tenant association
    return user.tenants[0].client_id

# --- SDUI: Metadata for Frontend ---
from app.modules.auth.utils import get_current_role_slug


def _build_prompt_form_fields(current_role: str) -> list[dict]:
    form_fields = [
        {
            "name": "slug",
            "label": "Slug / Nombre Unico",
            "type": "text",
            "required": True,
            "min_length": 3,
            "placeholder": "ej. bienvenida-cliente",
        },
        {
            "name": "prompt_text",
            "label": "Instrucciones del Prompt",
            "type": "textarea",
            "required": True,
            "min_length": 10,
            "rows": 8,
        },
        {
            "name": "is_active",
            "label": "Activo",
            "type": "switch",
            "default": True,
        },
    ]
    if current_role in ("admin", "system-user"):
        form_fields.insert(
            0,
            {
                "name": "client_id",
                "label": "Asignar a Cliente",
                "type": "select",
                "source": "/clients/simple-list",
                "required": True,
            },
        )
    return form_fields

@router.get("", response_model=dict)
async def get_ui_schema(user: User = Depends(current_active_user)):
    """
    Returns the Server-Driven UI definition for the Prompts Grid.
    """
    current_role = get_current_role_slug(user)
    
    # Define Filters (only for Global Admins)
    filters = []
    if current_role in ("admin", "system-user"):
        filters.append({
            "key": "client_id",
            "label": "Filtrar por Cliente",
            "source": "/clients/simple-list" 
        })

    form_fields = _build_prompt_form_fields(current_role)
    form_schema_b64 = encode_schema_b64(form_fields)

    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "grid-visual",
                "label": "AI Prompts Management",
                "properties": {
                    "data_url": "/prompts/data",
                    "filters": filters, 
                    "columns": [
                        {"id": "slug", "label": "Nombre Clave (Slug)", "type": "text"},
                        {"id": "client_name", "label": "Cliente", "type": "text", "sortable": True},
                        {"id": "prompt_text", "label": "Contenido del Prompt", "type": "text", "truncate": 50},
                        {"id": "is_active", "label": "Activo", "type": "badge", 
                         "badge_map": {"true": "success", "false": "danger"}}
                    ],
                    "actions": [
                        {
                            "label": "Editar", 
                            "action": "modal-form", 
                            "action_url": "/prompts/{id}",
                            "icon": "ri-pencil-fill",
                            "variant": "primary"
                        },
                        {
                            **delete_action("/prompts/{id}"),
                            "action": "api-call",
                            "method": "DELETE",
                            "confirm_message": "¿Estas seguro de eliminar este prompt?",
                            "icon": "ri-delete-bin-fill",
                            "variant": "danger",
                        },
                    ],
                    "header_actions": [
                        create_modal_action(
                            action_url="/prompts",
                            schema_b64=form_schema_b64,
                            modal_title="Crear Nuevo Prompt",
                            label="Nuevo Prompt",
                        )
                    ],
                    "form_schema": form_fields
                }
            }
        ]
    }

# --- API: CRUD Endpoints ---
from typing import Optional

@router.get("/data", response_model=List[PromptRow])
async def list_data(
    client_id: Optional[UUID] = None, # From Filter
    user: User = Depends(current_active_user)
):
    current_role = get_current_role_slug(user)
    target_client_id = None

    # Global Admins: Can select ANY client_id (or None for All)
    if current_role in ("admin", "system-user"):
         target_client_id = str(client_id) if client_id else None
    else:
    # Regular Users: Locked to their Tenant
        target_client_id = str(get_current_client_id(user))
        
    return await service.list_prompts(target_client_id)

@router.get("/{item_id}", response_model=PromptRow)
async def get_item(item_id: UUID, user: User = Depends(current_active_user)):
    current_role = get_current_role_slug(user)
    owner_client_id = str(get_current_client_id(user)) if current_role not in ("admin", "system-user") else None
    item = await service.get_prompt(owner_client_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return item

@router.post("", response_model=PromptRow)
async def create_item(item: PromptCreate, user: User = Depends(current_active_user)):
    target_client_id = None
    current_role = get_current_role_slug(user)

    # If Admin sends client_id, use it. Otherwise infer.
    if current_role in ("admin", "system-user") and item.client_id:
        target_client_id = str(item.client_id)
    else:
        target_client_id = str(get_current_client_id(user))
    
    return await service.create_prompt(target_client_id, item)

@router.put("/{item_id}", response_model=PromptRow)
async def update_item(item_id: UUID, item: PromptUpdate, user: User = Depends(current_active_user)):
    target_client_id = None
    current_role = get_current_role_slug(user)

    # In update, we need the "owner" client_id to find the record.
    # For Client Admin, it's always their tenant.
    # For Global Admin, the prompt might belong to any client. 
    # If they are editing, the service handles finding it. 
    # But we should allow them to CHANGE the client_id if they want (re-assignment)
    
    owner_client_id = str(get_current_client_id(user)) if current_role not in ("admin", "system-user") else None
    
    updated = await service.update_prompt(owner_client_id, item_id, item)
    if not updated:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return updated

@router.delete("/{item_id}")
async def delete_item(item_id: UUID, user: User = Depends(current_active_user)):
    current_role = get_current_role_slug(user)
    owner_client_id = str(get_current_client_id(user)) if current_role not in ("admin", "system-user") else None
    
    success = await service.delete_prompt(owner_client_id, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"status": "deleted"}

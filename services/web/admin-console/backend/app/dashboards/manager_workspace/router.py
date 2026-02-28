from fastapi import APIRouter, Depends, Request
from .schema import get_manager_workspace_schema, ManagerDashboardSchema
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User
from app.modules.leads_v2.router import (
    _resolve_vertical_schema_for_user,
    _build_dynamic_grid_config,
    _grid_props_to_renderer_config,
)

router = APIRouter()

@router.get("/manager", response_model=ManagerDashboardSchema)
async def get_manager_dashboard(
    request: Request,
    user: User = Depends(current_active_user),
):
    schema, vertical_slug, _vertical_name = await _resolve_vertical_schema_for_user(user)
    grid_config = _build_dynamic_grid_config(schema, vertical_slug)
    leads_grid_config = _grid_props_to_renderer_config(grid_config)
    return get_manager_workspace_schema(str(user.id), leads_grid_config)

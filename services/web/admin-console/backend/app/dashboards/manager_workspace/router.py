from fastapi import APIRouter, Depends, Request
from .schema import get_manager_workspace_schema, ManagerDashboardSchema
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User

router = APIRouter()

@router.get("/manager", response_model=ManagerDashboardSchema)
async def get_manager_dashboard(
    request: Request,
    user: User = Depends(current_active_user),
):
    return get_manager_workspace_schema(str(user.id))

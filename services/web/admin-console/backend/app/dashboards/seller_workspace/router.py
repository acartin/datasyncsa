from fastapi import APIRouter, Depends, Request, HTTPException
from uuid import UUID
from .schema import get_seller_workspace_schema, get_lead_detail_schema, ClientUserDashboardSchema
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User
from app.modules.leads.service import service as lead_service

router = APIRouter()

@router.get("/seller", response_model=ClientUserDashboardSchema)
async def get_seller_dashboard(request: Request, user: User = Depends(current_active_user)):
    return get_seller_workspace_schema(str(user.id))

@router.get("/leads/{lead_id}", response_model=ClientUserDashboardSchema)
async def get_lead_detail_dashboard(lead_id: UUID, user: User = Depends(current_active_user)):
    # Fetch deep lead data
    tenant_ids = [tenant.client_id for tenant in user.tenants] if user.tenants else []
    lead = await lead_service.get_lead_by_id(
        lead_id=lead_id,
        user_id=user.id,
        is_superuser=user.is_superuser,
        tenant_ids=tenant_ids,
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found or not assigned.")
    
    return get_lead_detail_schema(str(user.id), str(lead_id), lead)

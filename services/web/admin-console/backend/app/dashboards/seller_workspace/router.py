from fastapi import APIRouter, Depends, Request, HTTPException
from uuid import UUID
from .schema import (
    get_seller_workspace_schema,
    get_lead_detail_schema_v2_clone,
    ClientUserDashboardSchema,
)
from .schema_legacy import get_lead_detail_schema
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User
from app.modules.leads.service import service as lead_service
from app.modules.leads_v2.service import service as lead_v2_service

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


@router.get("/leads_v2/{lead_id}", response_model=ClientUserDashboardSchema)
async def get_lead_detail_dashboard_v2_clone(lead_id: UUID, user: User = Depends(current_active_user)):
    """
    Mirror of the legacy lead detail screen for v2 navigation.
    UI structure is intentionally identical; field mapping will be adjusted incrementally.
    """
    tenant_ids = [tenant.client_id for tenant in user.tenants] if user.tenants else []
    lead = await lead_v2_service.get_lead_detail_with_scoring_v2(
        lead_id=lead_id,
        user_id=user.id,
        is_superuser=user.is_superuser,
        tenant_ids=tenant_ids,
    )

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found or not assigned.")

    scoring_schema = None
    client_id = lead.get("client_id")
    if client_id:
        vertical_ctx = await lead_v2_service.get_client_vertical_context(client_id)
        if vertical_ctx and vertical_ctx.get("vertical_id"):
            scoring_schema = await lead_v2_service.get_scoring_schema_for_vertical(
                int(vertical_ctx["vertical_id"]),
                vertical_ctx.get("scoring_model_id"),
            )

    return get_lead_detail_schema_v2_clone(
        str(user.id),
        str(lead_id),
        lead,
        scoring_schema.model_dump() if scoring_schema else None,
    )

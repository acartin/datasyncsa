from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from app.modules.auth.router import fastapi_users
from app.modules.auth.models import User
from .schemas import GridPresetCreate, GridPresetResponse, GridPresetUpdate
from .service import GridPresetsService

router = APIRouter(prefix="/grid-presets", tags=["grid-presets"])

current_user = fastapi_users.current_user(active=True)

@router.post("", response_model=GridPresetResponse)
async def create_preset(
    preset: GridPresetCreate,
    user: User = Depends(current_user)
):
    # Get client_id from user's first tenant (multi-tenancy)
    if not user.tenants:
        raise HTTPException(status_code=403, detail="User has no associated tenant")
    
    client_id = user.tenants[0].client_id
    
    result = await GridPresetsService.create_preset(user.id, client_id, preset)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create preset")
    return result

@router.get("/{grid_id}", response_model=List[GridPresetResponse])
async def get_presets(
    grid_id: str,
    user: User = Depends(current_user)
):
    if not user.tenants:
        raise HTTPException(status_code=403, detail="User has no associated tenant")
    
    client_id = user.tenants[0].client_id
    
    return await GridPresetsService.get_user_presets(user.id, client_id, grid_id)

@router.delete("/{preset_id}")
async def delete_preset(
    preset_id: UUID,
    user: User = Depends(current_user)
):
    if not user.tenants:
        raise HTTPException(status_code=403, detail="User has no associated tenant")
    
    client_id = user.tenants[0].client_id
    
    result = await GridPresetsService.delete_preset(user.id, client_id, preset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Preset not found or not owned by user")
    return {"status": "success"}

@router.patch("/{preset_id}/default")
async def set_default_preset(
    preset_id: UUID,
    grid_id: str,
    user: User = Depends(current_user)
):
    if not user.tenants:
        raise HTTPException(status_code=403, detail="User has no associated tenant")
    
    client_id = user.tenants[0].client_id
    
    result = await GridPresetsService.set_default_preset(user.id, client_id, grid_id, preset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Preset not found or not owned by user")
    return {"status": "success"}

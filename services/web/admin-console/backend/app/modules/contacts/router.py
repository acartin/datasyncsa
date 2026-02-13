from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.auth.config import current_active_user
from app.modules.auth.models import User as AuthUser
from app.modules.auth.dependencies import RoleChecker
from app.modules.users.service import service as users_service
from app.modules.users.schemas import UserCreate
from . import service, schemas, categories

router = APIRouter()
router.include_router(categories.router)

@router.get("/contacts", response_model=List[schemas.ContactRead])
async def read_contacts(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[UUID] = Query(None, description="Filter by Client ID (Admin only)"),
    current_user: AuthUser = Depends(current_active_user)
):
    """
    List contacts.
    """
    target_client_id = client_id
    
    # Logic for implicit client context
    # Assumption: AuthUser might have 'client_id' or we derive it from tenants.
    # For this iteration, if not superuser and no client_id provided or derived, return empty.
    # Note: 'current_active_user' returns a User object.
    
    # Check if user is superuser
    if not current_user.is_superuser:
         # Try to find a client_id from their tenants
         # User -> tenants (ClientUser) -> client_id
         if current_user.tenants:
             # Basic logic: take the first tenant
             target_client_id = current_user.tenants[0].client_id
         else:
             # If simple user without tenants (unlikely in this system), invalid
             return []

    if not target_client_id and not current_user.is_superuser:
         return []

    if target_client_id:
        return await service.service.get_contacts_by_client(target_client_id, skip=skip, limit=limit)
    
    # Admin viewing everything? Service doesn't support it yet, returns empty list if no client_id.
    return []

@router.get("/contacts/{contact_id}", response_model=schemas.ContactRead)
async def read_contact(
    contact_id: UUID,
    current_user: AuthUser = Depends(current_active_user)
):
    target_client_id = None
    if not current_user.is_superuser:
        if current_user.tenants:
            target_client_id = current_user.tenants[0].client_id
        else:
            raise HTTPException(status_code=403, detail="No client context assigned.")

    contact = await service.service.get_contact_by_id(contact_id, target_client_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.post("/contacts", response_model=schemas.ContactRead)
async def create_contact(
    contact: schemas.ContactCreate,
    current_user: AuthUser = Depends(current_active_user)
):
    current_client_id = None
    if current_user.tenants:
        current_client_id = current_user.tenants[0].client_id
    
    return await service.service.create_contact(
        data=contact,
        current_user_client_id=current_client_id,
        is_superuser=current_user.is_superuser
    )

@router.put("/contacts/{contact_id}", response_model=schemas.ContactRead)
async def update_contact(
    contact_id: UUID,
    contact: schemas.ContactUpdate,
    current_user: AuthUser = Depends(current_active_user)
):
    current_client_id = None
    if current_user.tenants:
        current_client_id = current_user.tenants[0].client_id

    return await service.service.update_contact(
        contact_id=contact_id,
        data=contact,
        current_user_client_id=current_client_id,
        is_superuser=current_user.is_superuser
    )

@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: UUID,
    current_user: AuthUser = Depends(current_active_user)
):
    current_client_id = None
    if current_user.tenants:
        current_client_id = current_user.tenants[0].client_id

    await service.service.delete_contact(
        contact_id=contact_id,
        current_user_client_id=current_client_id,
        is_superuser=current_user.is_superuser
    )
    return {"status": "success", "message": "Contact deleted"}

@router.post("/contacts/{contact_id}/convert")
async def convert_contact_to_user(
    contact_id: UUID,
    data: schemas.ContactConvert,
    current_user: AuthUser = Depends(RoleChecker(["client-admin", "admin", "superadmin"]))
):
    """
    Promote a Contact to a System User. Restricted to Client Admins.
    """
    # 1. Verify Contact exists and belongs to the same client
    if not current_user.tenants:
        raise HTTPException(status_code=403, detail="User has no client context")
        
    client_id = current_user.tenants[0].client_id
    
    contact = await service.service.get_contact_by_id(contact_id, client_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found or access denied")

    # 2. Check if already has a user link (Optional but recommended)
    # TODO: Add check if needed

    # 3. Create User using UsersService
    # Forced role: client-user (ID: 94fb2738-073f-480a-868a-6271e3b362cf)
    CLIENT_USER_ROLE_ID = UUID("94fb2738-073f-480a-868a-6271e3b362cf")
    
    user_create = UserCreate(
        email=data.email,
        password=data.password,
        name=f"{contact.first_name} {contact.last_name or ''}",
        is_active=True,
        client_id=client_id,
        role_id=CLIENT_USER_ROLE_ID,
        contact_id=contact_id
    )

    try:
        new_user = await users_service.create_user(user_create)
        return {"status": "success", "message": "User created and linked", "user_id": new_user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

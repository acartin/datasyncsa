from fastapi import Depends, HTTPException, status
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User
from typing import List
import logging

logger = logging.getLogger(__name__)

class RoleChecker:
    """
    Dependency to enforcing RBAC.
    Usage: dependencies=[Depends(RoleChecker(["admin", "client-admin"]))]
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(current_active_user)):
        # Centralized Role Abstraction (handles Superuser internally)
        from app.modules.auth.utils import get_current_role_slug
        current_role = get_current_role_slug(user)
        
        # Check Role Consistency
        if current_role not in self.allowed_roles:
             logger.warning(
                 "RBAC deny",
                 extra={
                     "email": user.email,
                     "current_role": current_role,
                     "required_roles": self.allowed_roles,
                 },
             )
             raise HTTPException(
                 status_code=status.HTTP_403_FORBIDDEN, 
                 detail="Insufficient Permissions"
             )
            
        return user

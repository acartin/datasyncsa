from app.modules.auth.models import User
from typing import Optional

def get_current_role_slug(user: User) -> str:
    """
    Returns the effective role slug for the user.
    """
    # God Mode Re-enabled: Superusers are 'admin' regardless of tenant links
    if user.is_superuser:
        return "admin"

    if user.tenants and len(user.tenants) > 0:
        # Check against nested eager loaded role
        if user.tenants[0].role:
             return user.tenants[0].role.slug
    return "guest"

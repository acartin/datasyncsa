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
        slugs = []
        for tenant in user.tenants:
            role = getattr(tenant, "role", None)
            slug = getattr(role, "slug", None)
            if slug:
                slugs.append(slug)

        if slugs:
            # Deterministic precedence for multi-tenant users.
            # Keep system-user first so internal tooling (e.g. Verticales) is stable.
            role_priority = ["system-user", "system-admin", "admin", "client-admin", "client-user"]
            for preferred in role_priority:
                if preferred in slugs:
                    return preferred
            return sorted(slugs)[0]
    return "guest"

from typing import Optional

from app.modules.auth.models import User

SYSTEM_PUBLIC_CLIENT_ALIASES = {"datasyncsa", "datasync systems"}
CLIENT_ALLOWED_ACCESS_LEVELS = {"shared"}


def normalize_access_level(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def is_datasyncsa_tenant_user(user: User) -> bool:
    for tenant in (user.tenants or []):
        client = getattr(tenant, "client", None)
        client_name = (getattr(client, "name", "") or "").strip().lower()
        if client_name in SYSTEM_PUBLIC_CLIENT_ALIASES:
            return True
    return False


def resolve_datasyncsa_client_id(user: User) -> Optional[str]:
    for tenant in (user.tenants or []):
        client = getattr(tenant, "client", None)
        client_name = (getattr(client, "name", "") or "").strip().lower()
        if client_name in SYSTEM_PUBLIC_CLIENT_ALIASES:
            client_id = getattr(tenant, "client_id", None)
            return str(client_id) if client_id else None
    return None

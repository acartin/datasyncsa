from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


@dataclass(frozen=True)
class ClientContext:
    client_id: str
    role: str
    user_id: str
    email: str


VALID_ROLES = {
    "client-admin",
    "client-viewer",
    "system-admin",
    "system-user",
}


def require_client_context(
    authorization: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    x_role: str | None = Header(default=None, alias="X-Role"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
) -> ClientContext:
    settings = get_settings()

    if settings.api_token:
        expected = f"Bearer {settings.api_token}"
        if authorization != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Market Watch API token",
            )

    role = (x_role or settings.demo_role).strip()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role context",
        )

    client_id = (x_client_id or settings.demo_client_id or "1").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client context is required",
        )

    return ClientContext(
        client_id=client_id,
        role=role,
        user_id=(x_user_id or "demo-user").strip(),
        email=(x_user_email or "demo@market-watch.local").strip(),
    )

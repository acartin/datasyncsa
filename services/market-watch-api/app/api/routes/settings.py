from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.db import get_connection
from app.core.security import ClientContext, make_password_hash, require_client_context
from app.domain.placeholders import module_payload
from app.repositories.auth_repository import AuthRepository


router = APIRouter()


def get_repository() -> AuthRepository:
    return AuthRepository(get_connection)


def require_settings_admin(context: ClientContext) -> None:
    if context.role != "system-admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin role is required",
        )


class ClientCreate(BaseModel):
    client_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=160)
    market: str = Field(min_length=2, max_length=16)
    mode: str = Field(default="customer", pattern=r"^(customer|internal|demo)$")


class StatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(active|inactive|locked)$")


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    market: str | None = Field(default=None, min_length=2, max_length=16)
    mode: str | None = Field(default=None, pattern=r"^(customer|internal|demo)$")
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")


class RoleCreate(BaseModel):
    id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9:_-]*$")
    label: str = Field(min_length=2, max_length=160)
    scope: str = Field(pattern=r"^(system|client)$")
    description: str = Field(default="", max_length=400)


class RoleUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=160)
    scope: str | None = Field(default=None, pattern=r"^(system|client)$")
    description: str | None = Field(default=None, max_length=400)


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    email: str = Field(min_length=4, max_length=180)
    display_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=240)
    role_ids: list[str] = Field(min_length=1)
    client_id: int = Field(ge=1)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    password: str | None = Field(default=None, min_length=8, max_length=240)
    status: str | None = Field(default=None, pattern=r"^(active|inactive|locked)$")
    role_ids: list[str] | None = Field(default=None, min_length=1)
    client_id: int | None = Field(default=None, ge=1)


@router.get("/clients")
def clients(
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    return module_payload(
        context=context,
        module_id="settings.clients",
        title="Clientes",
        description="Clientes, mercados y tenants habilitados para el portal.",
        records=repository.list_clients(),
    )


@router.post("/clients")
def create_client(
    payload: ClientCreate,
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    return repository.create_client(
        client_key=payload.client_key,
        name=payload.name,
        market=payload.market,
        mode=payload.mode,
    )


@router.patch("/clients/{client_id}")
def update_client_status(
    client_id: int,
    payload: ClientUpdate,
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    client = repository.update_client(
        client_id=client_id,
        name=payload.name,
        market=payload.market,
        mode=payload.mode,
        status=payload.status,
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.get("/users")
def users(
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    return module_payload(
        context=context,
        module_id="settings.users",
        title="Usuarios",
        description="Usuarios locales de fase 0. El backend resuelve roles y tenant antes de exponer datos.",
        records=repository.list_users(),
    )


@router.post("/users")
def create_user(
    payload: UserCreate,
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    return repository.create_user(
        username=payload.username,
        email=payload.email,
        display_name=payload.display_name,
        password_hash=make_password_hash(payload.password),
        role_ids=payload.role_ids,
        client_id=payload.client_id,
    )


@router.patch("/users/{user_id}")
def update_user_status(
    user_id: int,
    payload: UserUpdate,
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    user = repository.update_user(
        user_id=user_id,
        display_name=payload.display_name,
        password_hash=make_password_hash(payload.password) if payload.password else None,
        status=payload.status,
        role_ids=payload.role_ids,
        client_id=payload.client_id,
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/roles")
def roles(
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    return module_payload(
        context=context,
        module_id="settings.roles",
        title="Roles",
        description="Roles y permisos base de negocio.",
        records=repository.list_roles(),
    )


@router.post("/roles")
def create_role(
    payload: RoleCreate,
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    return repository.create_role(
        role_id=payload.id,
        label=payload.label,
        scope=payload.scope,
        description=payload.description,
    )


@router.patch("/roles/{role_id}")
def update_role(
    role_id: str,
    payload: RoleUpdate,
    context: ClientContext = Depends(require_client_context),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, object]:
    require_settings_admin(context)
    role = repository.update_role(
        role_id=role_id,
        label=payload.label,
        scope=payload.scope,
        description=payload.description,
    )
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.get("/integrations")
def integrations(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="settings.integrations",
        title="Integraciones",
        description="Estado de integraciones externas del portal.",
        records=[
            {"id": "keycloak", "name": "Keycloak", "status": "planned"},
            {"id": "superset", "name": "Superset", "status": "external"},
            {"id": "dagster", "name": "Dagster", "status": "active"},
        ],
    )

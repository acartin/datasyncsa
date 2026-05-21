from fastapi import APIRouter, Depends

from app.core.security import ClientContext, require_client_context
from app.domain.placeholders import module_payload


router = APIRouter()


@router.get("/clients")
def clients(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="settings.clients",
        title="Clientes",
        description="Clientes, mercados y mapeos con grupos de Keycloak.",
        records=[
            {
                "id": "1",
                "name": "Cliente demo",
                "market": "CR",
                "keycloak_group": "/clients/demo",
                "status": "active",
            }
        ],
    )


@router.get("/users")
def users(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="settings.users",
        title="Usuarios",
        description="Vista placeholder. La identidad vivira en Keycloak.",
        records=[
            {
                "id": "demo-user",
                "email": "demo@market-watch.local",
                "source": "keycloak-planned",
                "role": context.role,
            }
        ],
    )


@router.get("/roles")
def roles(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="settings.roles",
        title="Roles",
        description="Roles previstos para Keycloak y autorizacion de negocio.",
        records=[
            {"id": "client-admin", "name": "client-admin", "scope": "client"},
            {"id": "client-viewer", "name": "client-viewer", "scope": "client"},
            {"id": "system-admin", "name": "system-admin", "scope": "system"},
            {"id": "system-user", "name": "system-user", "scope": "system"},
        ],
    )


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

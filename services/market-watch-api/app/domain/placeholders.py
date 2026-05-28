from app.core.config import get_settings
from app.core.security import ClientContext
from app.domain.navigation import ROLE_LABELS, menu_for_role


def user_payload(context: ClientContext) -> dict[str, object]:
    return {
        "user": {
            "id": context.user_id,
            "email": context.email,
            "role": context.role,
            "role_label": ROLE_LABELS.get(context.role, context.role),
        },
        "tenant": {
            "client_id": context.client_id,
            "name": context.client_name,
            "mode": "session",
        },
        "auth": {
            "provider": "market-watch-auth",
            "status": "active",
            "can_simulate_roles": context.can_simulate_roles,
            "is_role_simulated": context.is_role_simulated,
        },
    }


def menu_payload(context: ClientContext) -> dict[str, object]:
    return {
        **user_payload(context),
        "sections": menu_for_role(context.role),
    }


def module_payload(
    *,
    context: ClientContext,
    module_id: str,
    title: str,
    description: str,
    status: str = "placeholder",
    records: list[dict[str, object]] | None = None,
    actions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    settings = get_settings()
    return {
        "module": {
            "id": module_id,
            "title": title,
            "description": description,
            "status": status,
        },
        "context": {
            "client_id": context.client_id,
            "role": context.role,
        },
        "links": {
            "superset": settings.superset_base_url,
            "keycloak_issuer": settings.keycloak_issuer_url,
        },
        "actions": actions or [],
        "records": records or [],
    }


def dashboard_records() -> list[dict[str, object]]:
    return [
        {
            "id": "pricing-overview",
            "name": "Pricing Overview",
            "kind": "superset-dashboard",
            "status": "planned",
            "visibility": "client",
        },
        {
            "id": "competitor-matrix",
            "name": "Competitor Matrix",
            "kind": "superset-dashboard",
            "status": "planned",
            "visibility": "client",
        },
    ]


def report_records() -> list[dict[str, object]]:
    return [
        {
            "id": "daily-pricing-digest",
            "name": "Daily Pricing Digest",
            "cadence": "daily",
            "delivery": "email",
            "status": "planned",
        },
        {
            "id": "weekly-market-gaps",
            "name": "Weekly Market Gaps",
            "cadence": "weekly",
            "delivery": "superset-report",
            "status": "planned",
        },
    ]

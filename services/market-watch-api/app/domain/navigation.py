from dataclasses import dataclass


ROLE_LABELS = {
    "client-admin": "Client admin",
    "client-viewer": "Client viewer",
    "system-admin": "System admin",
    "system-user": "System operator",
}


@dataclass(frozen=True)
class MenuItem:
    id: str
    label: str
    href: str
    description: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class MenuSection:
    id: str
    label: str
    items: tuple[MenuItem, ...]


ALL_ROLES = ("client-admin", "client-viewer", "system-admin", "system-user")
CLIENT_ADMIN_ROLES = ("client-admin", "system-admin", "system-user")
SYSTEM_ADMIN_ROLES = ("system-admin",)
SYSTEM_ROLES = ("system-admin", "system-user")


MENU_SECTIONS = (
    MenuSection(
        id="analytics",
        label="Analytics",
        items=(
            MenuItem(
                id="executive-signals",
                label="Executive Signals",
                href="/pricing/executive-signals",
                description="Prioritized commercial signals for managers.",
                roles=ALL_ROLES,
            ),
            MenuItem(
                id="intraday-radar",
                label="Price and Promotion Radar",
                href="/pricing/intraday-radar",
                description="Day-over-day price and promotion changes for monitored products.",
                roles=ALL_ROLES,
            ),
            MenuItem(
                id="dashboards",
                label="Dashboards",
                href="/analytics/dashboards",
                description="Future Superset access and embeds for client analytics.",
                roles=ALL_ROLES,
            ),
            MenuItem(
                id="reports",
                label="Reports",
                href="/analytics/reports",
                description="Scheduled reports, deliveries and executive views.",
                roles=ALL_ROLES,
            ),
        ),
    ),
    MenuSection(
        id="operations",
        label="Operations",
        items=(
            MenuItem(
                id="campaigns",
                label="Campaigns",
                href="/operations/campaigns",
                description="Pricing campaign configuration and tracking.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="catalogs",
                label="Catalogs",
                href="/operations/catalogs",
                description="Sources, chains, locations and catalog status.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="monitored-products",
                label="Monitored Products",
                href="/operations/monitored-products",
                description="SKUs, GTINs and target products by client.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="competitors",
                label="Competitors",
                href="/operations/competitors",
                description="Active chains and competitors by market.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="runs",
                label="Runs",
                href="/operations/runs",
                description="ETL executions, operational status and Dagster links.",
                roles=ALL_ROLES,
            ),
        ),
    ),
    MenuSection(
        id="settings",
        label="Settings",
        items=(
            MenuItem(
                id="clients",
                label="Clients",
                href="/settings/clients",
                description="Clients, markets and identity mappings.",
                roles=SYSTEM_ADMIN_ROLES,
            ),
            MenuItem(
                id="users",
                label="Users",
                href="/settings/users",
                description="Operational user view; Keycloak will be the identity source.",
                roles=("client-admin", "system-admin"),
            ),
            MenuItem(
                id="roles",
                label="Roles",
                href="/settings/roles",
                description="Access roles and business permissions.",
                roles=("system-admin",),
            ),
            MenuItem(
                id="integrations",
                label="Integrations",
                href="/settings/integrations",
                description="Keycloak, Superset, Dagster and external connectors.",
                roles=SYSTEM_ROLES,
            ),
        ),
    ),
)


def menu_for_role(role: str) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    for section in MENU_SECTIONS:
        items = [
            {
                "id": item.id,
                "label": item.label,
                "href": item.href,
                "description": item.description,
            }
            for item in section.items
            if role in item.roles
        ]
        if items:
            sections.append({"id": section.id, "label": section.label, "items": items})
    return sections


def allowed_hrefs_for_role(role: str) -> set[str]:
    return {
        item.href
        for section in MENU_SECTIONS
        for item in section.items
        if role in item.roles
    }

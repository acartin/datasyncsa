from dataclasses import dataclass


ROLE_LABELS = {
    "client-admin": "Administrador del cliente",
    "client-viewer": "Usuario del cliente",
    "system-admin": "Administrador del sistema",
    "system-user": "Operador del sistema",
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
                description="Senales comerciales priorizadas para gerentes.",
                roles=ALL_ROLES,
            ),
            MenuItem(
                id="intraday-radar",
                label="Radar de precios y ofertas",
                href="/pricing/intraday-radar",
                description="Cambios dia contra dia de precio y promocion en productos monitoreados.",
                roles=ALL_ROLES,
            ),
            MenuItem(
                id="dashboards",
                label="Dashboards",
                href="/analytics/dashboards",
                description="Accesos y embeds futuros de Superset para analitica cliente.",
                roles=ALL_ROLES,
            ),
            MenuItem(
                id="reports",
                label="Reportes",
                href="/analytics/reportes",
                description="Reportes programados, entregas y vistas ejecutivas.",
                roles=ALL_ROLES,
            ),
        ),
    ),
    MenuSection(
        id="operations",
        label="Operacion",
        items=(
            MenuItem(
                id="campaigns",
                label="Campanas",
                href="/operacion/campanas",
                description="Configuracion y seguimiento de campanas de pricing.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="catalogs",
                label="Catalogos",
                href="/operacion/catalogos",
                description="Fuentes, cadenas, locations y estado de catalogos.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="monitored-products",
                label="Productos monitoreados",
                href="/operacion/productos-monitoreados",
                description="SKUs, GTINs y productos objetivo por cliente.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="competitors",
                label="Competidores",
                href="/operacion/competidores",
                description="Cadenas y competidores activos por mercado.",
                roles=CLIENT_ADMIN_ROLES,
            ),
            MenuItem(
                id="runs",
                label="Corridas",
                href="/operacion/corridas",
                description="Ejecuciones ETL, estado operativo y enlaces a Dagster.",
                roles=ALL_ROLES,
            ),
        ),
    ),
    MenuSection(
        id="settings",
        label="Configuracion",
        items=(
            MenuItem(
                id="clients",
                label="Clientes",
                href="/configuracion/clientes",
                description="Clientes, mercados y mapeos de identidad.",
                roles=SYSTEM_ADMIN_ROLES,
            ),
            MenuItem(
                id="users",
                label="Usuarios",
                href="/configuracion/usuarios",
                description="Vista operativa de usuarios; Keycloak sera la fuente de identidad.",
                roles=("client-admin", "system-admin"),
            ),
            MenuItem(
                id="roles",
                label="Roles",
                href="/configuracion/roles",
                description="Roles de acceso y permisos de negocio.",
                roles=("system-admin",),
            ),
            MenuItem(
                id="integrations",
                label="Integraciones",
                href="/configuracion/integraciones",
                description="Keycloak, Superset, Dagster y conectores externos.",
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

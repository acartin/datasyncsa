export const moduleEndpointByPath: Record<string, string> = {
  "/analytics/dashboards": "/analytics/dashboards",
  "/analytics/reportes": "/analytics/reports",
  "/operacion/campanas": "/operations/campaigns",
  "/operacion/catalogos": "/operations/catalogs",
  "/operacion/productos-monitoreados": "/operations/monitored-products",
  "/operacion/competidores": "/operations/competitors",
  "/operacion/corridas": "/operations/runs",
  "/configuracion/clientes": "/settings/clients",
  "/configuracion/usuarios": "/settings/users",
  "/configuracion/roles": "/settings/roles",
  "/configuracion/integraciones": "/settings/integrations"
};

export const roleOptions = [
  { id: "system-admin", label: "System admin" },
  { id: "system-user", label: "System user" },
  { id: "client-admin", label: "Client admin" },
  { id: "client-viewer", label: "Client viewer" }
] as const;

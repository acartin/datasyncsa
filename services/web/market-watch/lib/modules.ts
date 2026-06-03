export const moduleEndpointByPath: Record<string, string> = {
  "/analytics/dashboards": "/analytics/dashboards",
  "/analytics/reports": "/analytics/reports",
  "/operations/campaigns": "/operations/campaigns",
  "/operations/catalogs": "/operations/catalogs",
  "/operations/monitored-products": "/operations/monitored-products",
  "/operations/competitors": "/operations/competitors",
  "/operations/runs": "/operations/runs",
  "/settings/clients": "/settings/clients",
  "/settings/users": "/settings/users",
  "/settings/roles": "/settings/roles",
  "/settings/integrations": "/settings/integrations"
};

export const roleOptions = [
  { id: "system-admin", label: "System admin" },
  { id: "system-user", label: "System user" },
  { id: "client-admin", label: "Client admin" },
  { id: "client-viewer", label: "Client viewer" }
] as const;

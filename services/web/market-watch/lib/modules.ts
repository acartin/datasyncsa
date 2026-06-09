export const moduleEndpointByPath: Record<string, string> = {
  "/operations/campaigns": "/operations/campaigns",
  "/operations/campaign-access": "/operations/campaign-access",
  "/operations/monitored-products": "/operations/monitored-products",
  "/operations/locations-chains": "/operations/locations-chains",
  "/operations/catalog-sources": "/operations/catalog-sources",
  "/operations/runs-jobs": "/operations/runs-jobs",
  "/operations/data-quality": "/operations/data-quality",
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

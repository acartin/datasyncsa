import { MenuPayload, ModulePayload, Role } from "@/lib/types";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

function headersForRole(role: Role): HeadersInit {
  return {
    "X-Role": role,
    "X-Client-Id": "1",
    "X-User-Id": `demo-${role}`,
    "X-User-Email": `${role}@market-watch.local`
  };
}

async function getJson<T>(path: string, role: Role): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: headersForRole(role),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Market Watch API error ${response.status} on ${path}`);
  }

  return response.json() as Promise<T>;
}

export async function getMenu(role: Role): Promise<MenuPayload> {
  return getJson<MenuPayload>("/menu", role);
}

export async function getModule(path: string, role: Role): Promise<ModulePayload> {
  return getJson<ModulePayload>(path, role);
}

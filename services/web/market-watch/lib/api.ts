import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  ExecutiveSignalSearchParams,
  ExecutiveSignalsPayload,
  IntradayProductDetailPayload,
  IntradayRadarPayload,
  IntradayRadarSearchParams,
  SignalDetailPayload
} from "@/lib/pricing-types";
import { MenuPayload, ModulePayload } from "@/lib/types";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";
export const sessionCookieName = "mw_session";

async function authHeaders(): Promise<HeadersInit> {
  const cookieStore = await cookies();
  const token = cookieStore.get(sessionCookieName)?.value;
  if (!token) redirect("/login");

  return {
    Authorization: `Bearer ${token}`
  };
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: await authHeaders(),
    cache: "no-store"
  });

  if (response.status === 401) redirect("/login");
  if (response.status === 403) redirect("/pricing/executive-signals");

  if (!response.ok) {
    throw new Error(`Market Watch API error ${response.status} on ${path}`);
  }

  return response.json() as Promise<T>;
}

export async function getMenu(): Promise<MenuPayload> {
  return getJson<MenuPayload>("/menu");
}

export async function getModule(path: string): Promise<ModulePayload> {
  return getJson<ModulePayload>(path);
}

function queryString(params: Record<string, string | undefined>) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) searchParams.set(key, value);
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export async function getExecutiveSignals(params: ExecutiveSignalSearchParams): Promise<ExecutiveSignalsPayload> {
  return getJson<ExecutiveSignalsPayload>(`/datasets/executive-signals${queryString(params)}`);
}

export async function getSignalDetail(signalId: string): Promise<SignalDetailPayload> {
  return getJson<SignalDetailPayload>(`/datasets/executive-signals/${encodeURIComponent(signalId)}`);
}

export async function getIntradayRadar(params: IntradayRadarSearchParams): Promise<IntradayRadarPayload> {
  return getJson<IntradayRadarPayload>(`/datasets/intraday-radar${queryString(params)}`);
}

export async function getIntradayProductDetail(
  productKey: string,
  params: Pick<IntradayRadarSearchParams, "campaign_id" | "date_key" | "chain">
): Promise<IntradayProductDetailPayload> {
  return getJson<IntradayProductDetailPayload>(
    `/datasets/intraday-radar/products/${encodeURIComponent(productKey)}${queryString(params)}`
  );
}

import type { SavedTableViewsPayload } from "./data-views";

export async function getTableViews(viewKey: string): Promise<SavedTableViewsPayload> {
  return getJson<SavedTableViewsPayload>(`/table-views?view_key=${encodeURIComponent(viewKey)}`);
}

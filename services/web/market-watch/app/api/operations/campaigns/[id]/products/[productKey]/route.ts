import { sessionCookieName } from "@/lib/api";
import { feedbackQuery, friendlyApiError } from "@/lib/feedback";
import { redirectTo } from "@/lib/request-url";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

function tokenFromRequest(request: Request): string | undefined {
  return request.headers
    .get("cookie")
    ?.split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${sessionCookieName}=`))
    ?.split("=")[1];
}

function redirectWithFeedback(campaignId: string, type: "success" | "warning" | "error" | "info", message: string) {
  return redirectTo(`/operations/campaigns/${encodeURIComponent(campaignId)}?tab=products&${feedbackQuery(type, message)}`);
}

function normalizePayload(formData: FormData) {
  const payload: Record<string, unknown> = Object.fromEntries(formData.entries());
  for (const [key, value] of Object.entries(payload)) {
    if (typeof value === "string" && value.trim() === "") {
      delete payload[key];
    }
  }
  return payload;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; productKey: string }> }
) {
  const token = tokenFromRequest(request);
  if (!token) {
    return redirectTo("/login");
  }

  const { id, productKey } = await params;
  const payload = normalizePayload(await request.formData());
  const method = payload._method === "delete" ? "DELETE" : "PATCH";
  delete payload._method;

  const response = await fetch(
    `${API_BASE_URL}/operations/campaigns/${encodeURIComponent(id)}/products/${encodeURIComponent(productKey)}`,
    {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(method === "PATCH" ? { "Content-Type": "application/json" } : {})
      },
      body: method === "PATCH" ? JSON.stringify(payload) : undefined,
      cache: "no-store"
    }
  );

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => undefined);
    return redirectWithFeedback(id, "error", friendlyApiError(errorPayload));
  }

  return redirectWithFeedback(
    id,
    "success",
    method === "DELETE" ? "Campaign product removed successfully." : "Campaign product updated successfully."
  );
}

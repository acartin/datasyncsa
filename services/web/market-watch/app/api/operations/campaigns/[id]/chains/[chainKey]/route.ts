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
  return redirectTo(`/operations/campaigns/${encodeURIComponent(campaignId)}?tab=chains&${feedbackQuery(type, message)}`);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; chainKey: string }> }
) {
  const token = tokenFromRequest(request);
  if (!token) {
    return redirectTo("/login");
  }

  const { id, chainKey } = await params;

  const response = await fetch(
    `${API_BASE_URL}/operations/campaigns/${encodeURIComponent(id)}/chains/${encodeURIComponent(chainKey)}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`
      },
      cache: "no-store"
    }
  );

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => undefined);
    return redirectWithFeedback(id, "error", friendlyApiError(errorPayload));
  }

  return redirectWithFeedback(id, "success", "Campaign chain removed successfully.");
}

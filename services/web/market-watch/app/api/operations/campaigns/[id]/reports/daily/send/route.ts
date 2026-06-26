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

function redirectWithFeedback(
  campaignId: string,
  businessDate: string,
  type: "success" | "warning" | "error" | "info",
  message: string
) {
  const query = new URLSearchParams({
    tab: "report-preview",
    business_date: businessDate,
    ...Object.fromEntries(new URLSearchParams(feedbackQuery(type, message)).entries())
  });
  return redirectTo(`/operations/campaigns/${encodeURIComponent(campaignId)}?${query.toString()}`);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const token = tokenFromRequest(request);
  if (!token) {
    return redirectTo("/login");
  }

  const { id } = await params;
  const formData = await request.formData();
  const businessDate = String(formData.get("business_date") || "").trim();
  const query = businessDate ? `?business_date=${encodeURIComponent(businessDate)}` : "";
  const response = await fetch(`${API_BASE_URL}/operations/campaigns/${encodeURIComponent(id)}/reports/daily/send${query}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => undefined);
    return redirectWithFeedback(id, businessDate, "error", friendlyApiError(errorPayload));
  }

  return redirectWithFeedback(id, businessDate, "success", "Report email sent successfully.");
}

import { redirectTo } from "@/lib/request-url";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

export async function POST(request: Request) {
  const formData = await request.formData();
  const login = String(formData.get("login") ?? "").trim();

  const apiResponse = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login }),
    cache: "no-store"
  });

  if (!apiResponse.ok) {
    return redirectTo("/forgot-password?error=1");
  }

  const payload = (await apiResponse.json()) as { debug_reset_link?: string };
  const query = new URLSearchParams({ sent: "1" });
  if (payload.debug_reset_link) {
    query.set("debug", encodeURIComponent(payload.debug_reset_link));
  }

  return redirectTo(`/forgot-password?${query.toString()}`);
}

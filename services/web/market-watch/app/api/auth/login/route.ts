import { sessionCookieName } from "@/lib/api";
import { redirectTo } from "@/lib/request-url";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

export async function POST(request: Request) {
  const formData = await request.formData();
  const username = String(formData.get("username") ?? "");
  const password = String(formData.get("password") ?? "");

  const apiResponse = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    cache: "no-store"
  });

  if (!apiResponse.ok) {
    return redirectTo("/login?error=1");
  }

  const payload = (await apiResponse.json()) as { access_token: string; expires_at: string };
  const response = redirectTo("/pricing/executive-signals");
  response.cookies.set(sessionCookieName, payload.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.MARKET_WATCH_SECURE_COOKIES === "true",
    path: "/",
    expires: new Date(payload.expires_at)
  });

  return response;
}

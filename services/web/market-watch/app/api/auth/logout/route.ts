import { sessionCookieName } from "@/lib/api";
import { redirectTo } from "@/lib/request-url";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

async function logout(request: Request) {
  const token = request.headers
    .get("cookie")
    ?.split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${sessionCookieName}=`))
    ?.split("=")[1];

  if (token) {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
      cache: "no-store"
    }).catch(() => undefined);
  }

  const response = redirectTo("/");
  response.cookies.delete(sessionCookieName);
  return response;
}

export async function POST(request: Request) {
  return logout(request);
}

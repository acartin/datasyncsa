import { NextResponse } from "next/server";
import { sessionCookieName } from "@/lib/api";
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

function safeRedirect(path: string) {
  return path.startsWith("/") && !path.startsWith("//") ? path : "/pricing/executive-signals";
}

export async function POST(request: Request) {
  const token = tokenFromRequest(request);
  if (!token) {
    return redirectTo("/login");
  }

  const formData = await request.formData();
  const roleId = String(formData.get("role_id") ?? "");
  const redirectToPath = safeRedirect(String(formData.get("redirect_to") ?? "/pricing/executive-signals"));

  const response = await fetch(`${API_BASE_URL}/auth/simulate-role`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ role_id: roleId }),
    cache: "no-store"
  });

  if (response.status === 401) {
    return redirectTo("/login");
  }

  if (!response.ok) {
    return NextResponse.json(await response.json(), { status: response.status });
  }

  return redirectTo(roleId === "system-admin" ? redirectToPath : "/pricing/executive-signals");
}

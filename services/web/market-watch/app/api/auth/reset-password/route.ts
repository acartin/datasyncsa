import { redirectTo } from "@/lib/request-url";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

export async function POST(request: Request) {
  const formData = await request.formData();
  const token = String(formData.get("token") ?? "");
  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirm_password") ?? "");

  if (!token || password.length < 8 || password !== confirmPassword) {
    return redirectTo(`/reset-password?error=1&token=${encodeURIComponent(token)}`);
  }

  const apiResponse = await fetch(`${API_BASE_URL}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
    cache: "no-store"
  });

  if (!apiResponse.ok) {
    return redirectTo(`/reset-password?error=1&token=${encodeURIComponent(token)}`);
  }

  return redirectTo("/login?reset=1");
}

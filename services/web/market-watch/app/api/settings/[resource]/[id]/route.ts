import { NextResponse } from "next/server";
import { sessionCookieName } from "@/lib/api";
import { feedbackQuery, friendlyApiError } from "@/lib/feedback";
import { redirectTo } from "@/lib/request-url";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

const paths: Record<string, string> = {
  users: "/configuracion/usuarios",
  roles: "/configuracion/roles",
  clients: "/configuracion/clientes"
};

function redirectPath(resource: string) {
  return paths[resource] ?? "/configuracion/usuarios";
}

function redirectWithFeedback(resource: string, type: "success" | "warning" | "error" | "info", message: string) {
  return redirectTo(`${redirectPath(resource)}?${feedbackQuery(type, message)}`);
}

function tokenFromRequest(request: Request): string | undefined {
  return request.headers
    .get("cookie")
    ?.split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${sessionCookieName}=`))
    ?.split("=")[1];
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ resource: string; id: string }> }
) {
  const { resource, id } = await params;
  if (!["users", "clients", "roles"].includes(resource)) {
    return NextResponse.json({ detail: "Unknown settings resource" }, { status: 404 });
  }

  const token = tokenFromRequest(request);
  if (!token) {
    return redirectTo("/login");
  }

  const formData = await request.formData();
  const payload: Record<string, unknown> = Object.fromEntries(formData.entries());
  if (resource === "users") {
    payload.role_ids = formData.getAll("role_ids").map(String);
  }
  delete payload._method;
  if (payload.password === "") {
    delete payload.password;
  }

  const response = await fetch(`${API_BASE_URL}/settings/${resource}/${id}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => undefined);
    return redirectWithFeedback(resource, "error", friendlyApiError(payload));
  }

  return redirectWithFeedback(resource, "success", "Registro actualizado correctamente.");
}

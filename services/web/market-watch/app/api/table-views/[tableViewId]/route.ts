import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const API_BASE = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

async function authToken() {
  const cookieStore = await cookies();
  return cookieStore.get("mw_session")?.value;
}

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ tableViewId: string }> }) {
  const { tableViewId } = await params;
  const token = await authToken();
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const response = await fetch(`${API_BASE}/table-views/${tableViewId}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await response.json().catch(() => null), { status: response.status });
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ tableViewId: string }> }) {
  const { tableViewId } = await params;
  const token = await authToken();
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const response = await fetch(`${API_BASE}/table-views/${tableViewId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 204) return new NextResponse(null, { status: 204 });
  return NextResponse.json(await response.json().catch(() => null), { status: response.status });
}

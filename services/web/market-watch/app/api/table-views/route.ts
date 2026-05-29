import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const API_BASE = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

async function authHeaders() {
  const cookieStore = await cookies();
  const token = cookieStore.get("mw_session")?.value;
  if (!token) return null;
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function POST(req: NextRequest) {
  const headers = await authHeaders();
  if (!headers) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const response = await fetch(`${API_BASE}/table-views`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

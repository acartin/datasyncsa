import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { sessionCookieName } from "@/lib/api";

const API_BASE_URL = process.env.MARKET_WATCH_API_BASE_URL ?? "http://market-watch-api:8000/api/v1";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ productKey: string }> }
) {
  const cookieStore = await cookies();
  const token = cookieStore.get(sessionCookieName)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { productKey } = await params;
  const query = request.nextUrl.searchParams.toString();
  const response = await fetch(
    `${API_BASE_URL}/datasets/intraday-radar/products/${encodeURIComponent(productKey)}${query ? `?${query}` : ""}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    }
  );

  const data = await response.json().catch(() => ({ detail: "Invalid upstream response" }));
  return NextResponse.json(data, { status: response.status });
}

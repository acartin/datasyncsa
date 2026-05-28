import { NextResponse } from "next/server";

export function redirectTo(path: string, status = 303) {
  return new NextResponse(null, {
    status,
    headers: {
      Location: path
    }
  });
}

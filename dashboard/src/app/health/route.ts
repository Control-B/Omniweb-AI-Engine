import { NextResponse } from "next/server";

/** Load balancer / platform readiness (Next has no /health by default). */
export function GET() {
  return new NextResponse("ok", {
    status: 200,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
  });
}

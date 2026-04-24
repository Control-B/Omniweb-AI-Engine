import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Pass pathname into the root layout so we can skip ``AuthProvider`` on public routes.
 * That avoids a stuck ``loading`` gate when localStorage / token parsing misbehaves.
 */
export function middleware(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-omniweb-path", request.nextUrl.pathname);
  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|_next/data|favicon\\.ico|icon\\.svg|icon\\.png).*)"],
};

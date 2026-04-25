import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Clerk is required for `<SignIn />` / `<SignUp />` with `routing="path"`.
 * We do not protect routes here — the app uses its own JWT (AuthProvider) for
 * client/admin dashboards; `auth.protect()` is not used so password login still works.
 *
 * Also forwards pathname for `MaybeAuth` (public routes skip the auth context).
 */
export default clerkMiddleware((_, request: NextRequest) => {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-omniweb-path", request.nextUrl.pathname);
  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
});

export const config = {
  matcher: [
    // Skip Next internals and static files (Clerk + Next 14 default).
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};

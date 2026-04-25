import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import type { NextFetchEvent } from "next/server";

function injectPathHeader(request: NextRequest): NextResponse {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-omniweb-path", request.nextUrl.pathname);
  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

/**
 * Clerk middleware is only enabled when a publishable key exists at **build** time.
 * Otherwise `clerkMiddleware` can throw on every request → 500 on the whole app
 * (common on DO if `CLERK_PUBLISHABLE_KEY` was never set on the dashboard component).
 *
 * When Clerk is off, `<SignIn routing="path" />` may not work — use email/password or
 * add `CLERK_PUBLISHABLE_KEY` (BUILD_TIME) on the dashboard service and redeploy.
 */
const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim() ?? "";

const withClerk = clerkPublishableKey
  ? clerkMiddleware((_, request: NextRequest) => injectPathHeader(request))
  : null;

export default function middleware(request: NextRequest, event: NextFetchEvent) {
  if (withClerk) {
    return withClerk(request, event);
  }
  return injectPathHeader(request);
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};

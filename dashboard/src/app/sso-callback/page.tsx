import Link from "next/link";
import { SsoCallbackClient } from "./sso-callback-client";
import { INTERNAL_LOGIN_PATH } from "@/lib/auth-landing";
import { resolvedClerkPublishableKey } from "@/lib/clerk-publishable";

/**
 * SSO callback requires `<ClerkProvider>` in root layout (`resolvedClerkPublishableKey()`).
 * Same resolution as next.config env mapping (supports `CLERK_PUBLISHABLE_KEY`-only Docker builds).
 */
export default function SsoCallbackPage() {
  const clerkPk = resolvedClerkPublishableKey();

  if (!clerkPk) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background p-6 text-center">
        <p className="text-sm text-muted-foreground max-w-md">
          Single sign-on is not configured on this deployment (missing Clerk publishable key at
          build time). Use{" "}
          <Link href={INTERNAL_LOGIN_PATH} className="text-primary underline underline-offset-2">
            sign in
          </Link>
          , or redeploy the dashboard with{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
            CLERK_PUBLISHABLE_KEY
          </code>{" "}
          or{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
            NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
          </code>{" "}
          at build time.
        </p>
      </div>
    );
  }

  return <SsoCallbackClient />;
}

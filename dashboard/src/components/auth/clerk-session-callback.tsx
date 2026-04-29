"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth as useClerkAuth } from "@clerk/nextjs";
import { exchangeClerkSession, getMeWorkspace } from "@/lib/api";
import { isInternalRole } from "@/lib/auth-context";

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());

export function ClerkSessionCallback() {
  const router = useRouter();
  const { isLoaded, userId, getToken } = useClerkAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function run() {
      if (!clerkEnabled) {
        router.replace("/login");
        return;
      }
      if (!isLoaded) return;
      if (!userId) {
        router.replace("/login");
        return;
      }

      try {
        const clerkToken = await getToken();
        if (!clerkToken) throw new Error("Missing Clerk session token");
        const data = await exchangeClerkSession(clerkToken);
        if (isInternalRole(data.role)) {
          router.replace("/admin");
          return;
        }
        try {
          const ws = await getMeWorkspace();
          router.replace(ws.needs_onboarding ? "/onboarding" : "/dashboard");
        } catch {
          router.replace("/dashboard");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not start your session");
      }
    }

    void run();
  }, [getToken, isLoaded, router, userId]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 text-center shadow-sm">
        {error ? (
          <>
            <h1 className="text-lg font-semibold text-foreground">Session setup failed</h1>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
            <button
              type="button"
              onClick={() => router.replace("/login")}
              className="mt-4 text-sm text-primary hover:underline"
            >
              Back to login
            </button>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
            <h1 className="mt-4 text-lg font-semibold text-foreground">Starting your dashboard</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              We&apos;re creating your Omniweb engine session now.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

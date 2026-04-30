"use client";

import { useAuth as useClerkAuth } from "@clerk/nextjs";
import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { signIntoEngineWithClerk } from "@/lib/clerk-engine-exchange";
import { INTERNAL_LOGIN_PATH } from "@/lib/auth-landing";

const hasClerk =
  typeof process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY === "string" &&
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.trim().length > 0;

/**
 * Bridges Clerk ↔ engine JWT without visiting omniweb.ai.
 * Redirect here when Omniweb JWT is missing but a Clerk session may exist
 * (e.g. user signed in on engine `/sign-in` or resumed on this host).
 */
export default function ClerkHandoffPage() {
  const router = useRouter();
  const { user, loading, refresh } = useAuth();
  const clerk = useClerkAuth();
  const [error, setError] = useState<string | null>(null);
  const exchangeStarted = useRef(false);

  useEffect(() => {
    if (!hasClerk) {
      router.replace(INTERNAL_LOGIN_PATH);
      return;
    }
    if (loading) return;
    if (user) {
      router.replace("/dashboard");
      return;
    }
    if (!clerk.isLoaded) return;
    if (!clerk.userId) {
      router.replace("/sign-in");
      return;
    }
    if (exchangeStarted.current) return;
    exchangeStarted.current = true;
    void (async () => {
      try {
        await signIntoEngineWithClerk(clerk.getToken);
        refresh();
        router.replace("/dashboard");
      } catch (e) {
        const msg =
          e instanceof Error ? e.message : "Missing or invalid session.";
        setError(msg);
        exchangeStarted.current = false;
        router.replace("/sign-in");
      }
    })();
  }, [
    clerk.isLoaded,
    clerk.userId,
    clerk.getToken,
    loading,
    user,
    refresh,
    router,
  ]);

  if (!hasClerk) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-sm text-destructive max-w-md">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-3 px-6">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Opening your Omniweb dashboard…</p>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AuthenticateWithRedirectCallback,
  useAuth,
  useUser,
} from "@clerk/nextjs";
import { Loader2 } from "lucide-react";
import { signIntoEngineWithClerk } from "@/lib/clerk-engine-exchange";

function SsoCallbackExchange() {
  const { isLoaded, isSignedIn, user } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !user || ran.current) return;
    ran.current = true;
    (async () => {
      try {
        await signIntoEngineWithClerk(getToken);
        router.replace("/dashboard");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not complete sign-in");
      }
    })();
  }, [isLoaded, isSignedIn, user, getToken, router]);

  if (error) {
    return (
      <p className="text-sm text-red-400 text-center max-w-sm px-4">
        {error}
      </p>
    );
  }

  return <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />;
}

/** Only mount when RootLayout renders `<ClerkProvider>` (same env as publishable key). */
export function SsoCallbackClient() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background p-6">
      <AuthenticateWithRedirectCallback />
      <SsoCallbackExchange />
      <p className="text-sm text-muted-foreground">Completing sign in…</p>
    </div>
  );
}

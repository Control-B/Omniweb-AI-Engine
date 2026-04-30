"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { setToken } from "@/lib/api";

/**
 * Marketing site (other origin) completes Clerk, exchanges for an engine JWT on their
 * domain, then redirects here with the token in the URL hash. We persist and continue.
 */
export default function AuthEmbeddedPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined" || ran.current) return;
    ran.current = true;

    const h = window.location.hash;
    if (!h || h.length < 2) {
      setError("Missing session. Please open the app from the marketing sign-in again.");
      return;
    }
    const params = new URLSearchParams(h.replace(/^#/, ""));
    const token = params.get("access_token");
    if (!token) {
      setError("Invalid handoff. Please try signing in again.");
      return;
    }
    setToken(token);
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    router.replace("/dashboard");
  }, [router]);

  if (error) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center gap-3 p-6">
        <p className="text-sm text-destructive text-center max-w-md">{error}</p>
        <a href="/sign-in" className="text-sm text-primary hover:underline">
          Go to sign in
        </a>
      </div>
    );
  }

  return (
    <div className="min-h-dvh flex flex-col items-center justify-center gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Opening your dashboard…</p>
    </div>
  );
}

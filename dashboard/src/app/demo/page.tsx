"use client";

import { useEffect, useState } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { demoLogin, stashAdminToken } from "@/lib/api";

export default function DemoPage() {
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function autoLogin() {
      try {
        // Save any existing admin session so we can return later
        stashAdminToken();
        await demoLogin();
        if (!cancelled) {
          const target = new URLSearchParams(window.location.search).get("target");
          const page = target === "agent" ? "?page=agent" : "";
          // Full page navigation so auth context picks up the token
          window.location.href = `/dashboard${page}`;
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || "Failed to start demo session");
        }
      }
    }

    autoLogin();
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <div className="w-full max-w-sm space-y-4 text-center">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-destructive/20 text-destructive mx-auto">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">Demo Unavailable</h2>
          <p className="text-sm text-muted-foreground">{error}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => { setError(""); window.location.reload(); }}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Retry
            </button>
            <a
              href="/login"
              className="px-4 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-sidebar-accent transition-colors"
            >
              Go to Login
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background gap-3">
      <Loader2 className="w-6 h-6 animate-spin text-primary" />
      <p className="text-sm text-muted-foreground">Starting demo session…</p>
    </div>
  );
}

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useClerk } from "@clerk/nextjs";
import { clearToken } from "@/lib/api";

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());

export function ClerkLogout() {
  const router = useRouter();
  const clerk = useClerk();

  useEffect(() => {
    async function run() {
      clearToken();
      if (typeof window !== "undefined") {
        localStorage.removeItem("omniweb_setup_complete");
        localStorage.removeItem("omniweb_admin_token_stash");
      }

      if (!clerkEnabled) {
        router.replace("/login");
        return;
      }

      try {
        await clerk.signOut({ redirectUrl: "/login" });
      } catch {
        router.replace("/login");
      }
    }

    void run();
  }, [clerk, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="rounded-2xl border border-border bg-card p-6 text-center shadow-sm">
        <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
        <p className="mt-3 text-sm text-muted-foreground">Signing you out…</p>
      </div>
    </div>
  );
}

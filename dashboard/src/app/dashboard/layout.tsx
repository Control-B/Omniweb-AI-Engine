"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";
import { isInternalRole, useAuth } from "@/lib/auth-context";
import { ClientSidebar } from "@/components/client-sidebar";
import { TrialBanner } from "@/components/dashboard/trial-banner";
import { getMeWorkspace, type WorkspaceResponse } from "@/lib/api";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [authChecked, setAuthChecked] = useState(false);
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    if (!user?.client_id) return;
    try {
      setWsError(null);
      const ws = await getMeWorkspace();
      setWorkspace(ws);
      if (ws.needs_onboarding) {
        router.replace("/onboarding");
        return;
      }
    } catch (e) {
      setWsError(e instanceof Error ? e.message : "Could not load workspace");
    }
  }, [user?.client_id, router]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (isInternalRole(user.role)) {
      router.replace("/admin");
      return;
    }
    setAuthChecked(true);
  }, [user, loading, router]);

  useEffect(() => {
    if (authChecked) void loadWorkspace();
  }, [authChecked, loadWorkspace]);

  if (loading || !authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (wsError) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 p-6">
        <p className="text-sm text-destructive">{wsError}</p>
        <button
          type="button"
          className="text-sm text-primary underline"
          onClick={() => void loadWorkspace()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (workspace?.needs_onboarding) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TrialBanner workspace={workspace} />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Suspense
          fallback={
            <div className="w-[240px] shrink-0 border-r border-border bg-sidebar flex items-center justify-center">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          }
        >
          <ClientSidebar pathname={pathname} />
        </Suspense>
        <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

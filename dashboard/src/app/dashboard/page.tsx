"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { isInternalRole, useAuth } from "@/lib/auth-context";
import { ClientSidebar } from "@/components/client-sidebar";
import { DashboardPage } from "@/components/pages/dashboard";
import { CallsPage } from "@/components/pages/calls";
import { LeadsPage } from "@/components/pages/leads";
import { AgentConfigPage } from "@/components/pages/agent-config";
import { NumbersPage } from "@/components/pages/numbers";
import { SettingsPage } from "@/components/pages/settings";
import { AutomationsPage } from "@/components/pages/automations";
import { SitesPage } from "@/components/pages/sites";
import { OnboardingFlow } from "@/components/pages/onboarding";
import { Loader2 } from "lucide-react";
import { getAgentConfig } from "@/lib/api";

export type ClientPageId =
  | "dashboard"
  | "calls"
  | "leads"
  | "agent"
  | "numbers"
  | "sites"
  | "automations"
  | "settings";

export default function ClientDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activePage, setActivePage] = useState<ClientPageId>("dashboard");
  const [authChecked, setAuthChecked] = useState(false);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [onboardingChecked, setOnboardingChecked] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (isInternalRole(user.role)) {
      router.replace("/admin");
    } else {
      setAuthChecked(true);
    }
  }, [user, loading, router]);

  // Check if user has completed onboarding
  const checkOnboarding = useCallback(async () => {
    if (!user?.client_id) return;

    // Fast path: localStorage flag means they already completed setup
    if (localStorage.getItem("omniweb_setup_complete") === "1") {
      setNeedsOnboarding(false);
      setOnboardingChecked(true);
      return;
    }

    // Slow path: check if agent config exists with a real agent
    try {
      const config = await getAgentConfig(user.client_id);
      const hasAgent = !!(config?.agent_name && config.agent_name !== "");
      if (hasAgent) {
        // Agent exists — mark as done so we don't check again
        localStorage.setItem("omniweb_setup_complete", "1");
        setNeedsOnboarding(false);
      } else {
        setNeedsOnboarding(true);
      }
    } catch {
      // No config at all — needs onboarding
      setNeedsOnboarding(true);
    }
    setOnboardingChecked(true);
  }, [user?.client_id]);

  useEffect(() => {
    if (authChecked) checkOnboarding();
  }, [authChecked, checkOnboarding]);

  if (loading || !authChecked || !onboardingChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Show onboarding for first-time users
  if (needsOnboarding) {
    return (
      <OnboardingFlow
        onComplete={() => {
          setNeedsOnboarding(false);
        }}
      />
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <ClientSidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="min-w-0 flex-1 overflow-y-auto">
        {activePage === "dashboard" && <DashboardPage />}
        {activePage === "calls" && <CallsPage />}
        {activePage === "leads" && <LeadsPage />}
        {activePage === "agent" && <AgentConfigPage />}
        {activePage === "numbers" && <NumbersPage />}
          {activePage === "sites" && <SitesPage />}
        {activePage === "automations" && <AutomationsPage />}
        {activePage === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}

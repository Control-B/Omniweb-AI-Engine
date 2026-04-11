"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ClientSidebar } from "@/components/client-sidebar";
import { DashboardPage } from "@/components/pages/dashboard";
import { CallsPage } from "@/components/pages/calls";
import { LeadsPage } from "@/components/pages/leads";
import { AgentConfigPage } from "@/components/pages/agent-config";
import { NumbersPage } from "@/components/pages/numbers";
import { SettingsPage } from "@/components/pages/settings";
import { AutomationsPage } from "@/components/pages/automations";
import { Loader2 } from "lucide-react";

export type ClientPageId =
  | "dashboard"
  | "calls"
  | "leads"
  | "agent"
  | "numbers"
  | "automations"
  | "settings";

export default function ClientDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activePage, setActivePage] = useState<ClientPageId>("dashboard");
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (user.role === "admin") {
      router.replace("/admin");
    } else {
      setAuthChecked(true);
    }
  }, [user, loading, router]);

  if (loading || !authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <ClientSidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="flex-1 overflow-y-auto">
        {activePage === "dashboard" && <DashboardPage />}
        {activePage === "calls" && <CallsPage />}
        {activePage === "leads" && <LeadsPage />}
        {activePage === "agent" && <AgentConfigPage />}
        {activePage === "numbers" && <NumbersPage />}
        {activePage === "automations" && <AutomationsPage />}
        {activePage === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}

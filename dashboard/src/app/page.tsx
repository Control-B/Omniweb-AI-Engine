"use client";

import { useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { DashboardPage } from "@/components/pages/dashboard";
import { CallsPage } from "@/components/pages/calls";
import { LeadsPage } from "@/components/pages/leads";
import { AgentConfigPage } from "@/components/pages/agent-config";
import { NumbersPage } from "@/components/pages/numbers";
import { SettingsPage } from "@/components/pages/settings";
import { AutomationsPage } from "@/components/pages/automations";

export type PageId =
  | "dashboard"
  | "calls"
  | "leads"
  | "agent"
  | "numbers"
  | "automations"
  | "settings";

export default function Home() {
  const [activePage, setActivePage] = useState<PageId>("dashboard");

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
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

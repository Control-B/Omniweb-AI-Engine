"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { hasPermission, isInternalRole, useAuth, type UserPermission } from "@/lib/auth-context";
import { AdminSidebar } from "@/components/admin-sidebar";
import { AdminOverview } from "@/components/admin/overview";
import { AdminClients } from "@/components/admin/clients";
import { AdminTemplates } from "@/components/admin/templates";
import { AdminClientDetail } from "@/components/admin/client-detail";
import { AdminAgents } from "@/components/admin/agents";
import { AdminConversations } from "@/components/admin/conversations";
import { AdminTeam } from "@/components/admin/team";
import { AdminAccount } from "@/components/admin/account";
import { AgentConfigPage } from "@/components/pages/agent-config";
import { Loader2 } from "lucide-react";

export type AdminPageId =
  | "overview"
  | "agent-config"
  | "ai-telephony"
  | "agents"
  | "sessions"
  | "clients"
  | "templates"
  | "team"
  | "account"
  | "client-detail";

const PAGE_PERMISSIONS: Partial<Record<Exclude<AdminPageId, "client-detail">, UserPermission>> = {
  overview: "overview.read",
  "agent-config": "agents.read",
  "ai-telephony": "agents.read",
  agents: "agents.read",
  sessions: "conversations.read",
  clients: "clients.read",
  templates: "templates.read",
  team: "team.read",
};

export default function AdminDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activePage, setActivePage] = useState<AdminPageId>("overview");
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (!isInternalRole(user.role)) {
      router.replace("/dashboard");
    } else {
      setAuthChecked(true);
    }
  }, [user, loading, router]);

    useEffect(() => {
      if (!user) return;
      if (activePage === "client-detail") {
        if (!hasPermission(user, "clients.read")) {
          setSelectedClientId(null);
          setActivePage("overview");
        }
        return;
      }

      const permission = PAGE_PERMISSIONS[activePage];
      if (permission && !hasPermission(user, permission)) {
        const fallback = (Object.entries(PAGE_PERMISSIONS).find(([, nextPermission]) => nextPermission && hasPermission(user, nextPermission))?.[0] ?? "overview") as AdminPageId;
        setActivePage(fallback);
      }
    }, [activePage, user]);

  if (loading || !authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  function handleViewClient(clientId: string) {
    setSelectedClientId(clientId);
    setActivePage("client-detail");
  }

  function handleBackToClients() {
    setSelectedClientId(null);
    setActivePage("clients");
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <AdminSidebar activePage={activePage} onNavigate={(p) => { setActivePage(p); setSelectedClientId(null); }} />
      <main className="flex-1 overflow-y-auto">
        {activePage === "overview" && <AdminOverview />}
        {activePage === "agent-config" && <AgentConfigPage />}
        {activePage === "ai-telephony" && <AgentConfigPage initialTab="telephony" />}
        {activePage === "agents" && <AdminAgents />}
        {activePage === "sessions" && <AdminConversations />}
        {activePage === "clients" && <AdminClients onViewClient={handleViewClient} />}
        {activePage === "templates" && <AdminTemplates />}
        {activePage === "team" && <AdminTeam />}
        {activePage === "account" && <AdminAccount />}
        {activePage === "client-detail" && selectedClientId && (
          <AdminClientDetail clientId={selectedClientId} onBack={handleBackToClients} />
        )}
      </main>
    </div>
  );
}

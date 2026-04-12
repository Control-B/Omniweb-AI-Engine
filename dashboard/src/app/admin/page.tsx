"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AdminSidebar } from "@/components/admin-sidebar";
import { AdminOverview } from "@/components/admin/overview";
import { AdminClients } from "@/components/admin/clients";
import { AdminTemplates } from "@/components/admin/templates";
import { AdminClientDetail } from "@/components/admin/client-detail";
import { AdminAgents } from "@/components/admin/agents";
import { AdminConversations } from "@/components/admin/conversations";
import { Loader2 } from "lucide-react";

export type AdminPageId = "overview" | "agents" | "sessions" | "clients" | "templates" | "client-detail";

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
    } else if (user.role !== "admin") {
      router.replace("/dashboard");
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
        {activePage === "agents" && <AdminAgents />}
        {activePage === "sessions" && <AdminConversations />}
        {activePage === "clients" && <AdminClients onViewClient={handleViewClient} />}
        {activePage === "templates" && <AdminTemplates />}
        {activePage === "client-detail" && selectedClientId && (
          <AdminClientDetail clientId={selectedClientId} onBack={handleBackToClients} />
        )}
      </main>
    </div>
  );
}

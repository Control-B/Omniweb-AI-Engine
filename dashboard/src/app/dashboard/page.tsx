"use client";

import { useState, useEffect } from "react";
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
import { Loader2 } from "lucide-react";

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

  if (loading || !authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Your AI revenue agent is ready to configure.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Setup progress</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-2">
            {steps.map((s, i) => (
              <li key={s.key} className="flex items-center gap-3 text-sm">
                <span
                  className={
                    progress && progress[s.key]
                      ? "text-emerald-400"
                      : "text-muted-foreground"
                  }
                >
                  {i + 1}.
                </span>
                <span className={progress && progress[s.key] ? "text-foreground" : "text-muted-foreground"}>
                  {s.label}
                </span>
                {progress && progress[s.key] ? (
                  <span className="text-xs text-emerald-500">Done</span>
                ) : (
                  <span className="text-xs text-muted-foreground">Pending</span>
                )}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Link href="/dashboard/widget/configure">
          <Card className="h-full transition-colors hover:border-primary/40 cursor-pointer">
            <CardContent className="p-5 flex items-start gap-3">
              <Bot className="w-8 h-8 text-primary shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Configure AI Agent</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Name, instructions, tone, and widget appearance
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard/widget/test">
          <Card className="h-full transition-colors hover:border-primary/40 cursor-pointer">
            <CardContent className="p-5 flex items-start gap-3">
              <MessageSquareText className="w-8 h-8 text-primary shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Test Widget</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Private preview before you go live
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard/widget/embed">
          <Card className="h-full transition-colors hover:border-primary/40 cursor-pointer">
            <CardContent className="p-5 flex items-start gap-3">
              <Code className="w-8 h-8 text-primary shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Get Embed Code</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Install your widget and start capturing leads
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard?page=leads">
          <Card className="h-full transition-colors hover:border-primary/40 cursor-pointer">
            <CardContent className="p-5 flex items-start gap-3">
              <LineChart className="w-8 h-8 text-primary shrink-0" />
              <div>
                <p className="font-semibold text-foreground">View Conversations</p>
                <p className="text-xs text-muted-foreground mt-1">Leads and call history</p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard?page=settings">
          <Card className="h-full transition-colors hover:border-primary/40 cursor-pointer">
            <CardContent className="p-5 flex items-start gap-3">
              <Settings className="w-8 h-8 text-primary shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Business Settings</p>
                <p className="text-xs text-muted-foreground mt-1">Profile and notifications</p>
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>

      <DashboardPage />
    </div>
  );
}

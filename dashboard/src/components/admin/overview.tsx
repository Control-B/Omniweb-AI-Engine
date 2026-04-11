"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { adminGetStats } from "@/lib/api";
import {
  Users,
  Phone,
  UserCheck,
  Hash,
  TrendingUp,
  Loader2,
  AlertCircle,
} from "lucide-react";

interface PlatformStats {
  total_clients: number;
  total_calls: number;
  total_leads: number;
  total_numbers: number;
  clients_by_plan: Record<string, number>;
}

export function AdminOverview() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    adminGetStats()
      .then(setStats)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  const statCards = [
    {
      label: "Total Clients",
      value: stats.total_clients,
      icon: Users,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "Total Calls",
      value: stats.total_calls,
      icon: Phone,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
    },
    {
      label: "Total Leads",
      value: stats.total_leads,
      icon: UserCheck,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
    },
    {
      label: "Phone Numbers",
      value: stats.total_numbers,
      icon: Hash,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
    },
  ];

  const planColors: Record<string, "default" | "success" | "warning" | "secondary"> = {
    starter: "secondary",
    growth: "default",
    pro: "success",
    agency: "warning",
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Platform Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Real-time metrics across all tenants
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s) => (
          <Card key={s.label}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground font-medium">{s.label}</p>
                  <p className="text-2xl font-bold text-foreground mt-1">
                    {s.value.toLocaleString()}
                  </p>
                </div>
                <div className={`${s.bg} ${s.color} p-3 rounded-xl`}>
                  <s.icon className="w-5 h-5" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Clients by Plan */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-primary" />
            Clients by Plan
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Object.entries(stats.clients_by_plan).map(([plan, count]) => (
              <div
                key={plan}
                className="rounded-xl border border-border bg-card p-4 text-center"
              >
                <Badge variant={planColors[plan] || "secondary"} className="mb-2">
                  {plan}
                </Badge>
                <p className="text-2xl font-bold text-foreground">{count}</p>
                <p className="text-xs text-muted-foreground mt-1">clients</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Quick insights */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Engagement Ratios</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="text-muted-foreground">Calls per Client</span>
                  <span className="font-medium text-foreground">
                    {stats.total_clients > 0
                      ? (stats.total_calls / stats.total_clients).toFixed(1)
                      : "0"}
                  </span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        stats.total_clients > 0
                          ? (stats.total_calls / stats.total_clients) * 10
                          : 0
                      )}%`,
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="text-muted-foreground">Leads per Client</span>
                  <span className="font-medium text-foreground">
                    {stats.total_clients > 0
                      ? (stats.total_leads / stats.total_clients).toFixed(1)
                      : "0"}
                  </span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        stats.total_clients > 0
                          ? (stats.total_leads / stats.total_clients) * 10
                          : 0
                      )}%`,
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="text-muted-foreground">Numbers per Client</span>
                  <span className="font-medium text-foreground">
                    {stats.total_clients > 0
                      ? (stats.total_numbers / stats.total_clients).toFixed(1)
                      : "0"}
                  </span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        stats.total_clients > 0
                          ? (stats.total_numbers / stats.total_clients) * 10
                          : 0
                      )}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Platform Health</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                <span className="text-sm text-muted-foreground">API Status</span>
                <Badge variant="success">Operational</Badge>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                <span className="text-sm text-muted-foreground">Database</span>
                <Badge variant="success">Connected</Badge>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                <span className="text-sm text-muted-foreground">Auth Service</span>
                <Badge variant="success">Active</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

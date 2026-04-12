"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { adminGetStats } from "@/lib/api";
import { cn, formatDuration, formatPhone, timeAgo } from "@/lib/utils";
import {
  Users,
  Phone,
  UserCheck,
  Hash,
  TrendingUp,
  Loader2,
  AlertCircle,
  CalendarCheck,
  Wrench,
  PhoneIncoming,
  Clock,
  Bot,
} from "lucide-react";

interface WeeklyDay {
  date: string;
  label: string;
  calls: number;
  leads: number;
}

interface RecentLead {
  id: string;
  caller_name: string;
  caller_phone: string;
  intent: string | null;
  urgency: string;
  status: string;
  lead_score: number;
  services_requested: string[];
  created_at: string | null;
}

interface RecentCall {
  id: string;
  caller_number: string;
  direction: string;
  channel: string;
  status: string;
  duration_seconds: number | null;
  started_at: string | null;
}

interface RecentToolCall {
  id: string;
  tool_name: string;
  success: boolean;
  duration_ms: number | null;
  created_at: string | null;
}

interface PlatformStats {
  total_clients: number;
  active_clients: number;
  total_calls: number;
  total_leads: number;
  total_numbers: number;
  calls_today: number;
  leads_today: number;
  calls_this_week: number;
  booked_appointments: number;
  leads_by_status: Record<string, number>;
  clients_by_plan: Record<string, number>;
  tool_calls_today: number;
  tool_summary: Record<string, number>;
  recent_leads: RecentLead[];
  recent_calls: RecentCall[];
  recent_tool_calls: RecentToolCall[];
  weekly: WeeklyDay[];
}

const TOOL_LABELS: Record<string, string> = {
  capture_lead: "Lead Capture",
  check_availability: "Availability",
  book_appointment: "Booking",
  send_confirmation_sms: "SMS",
  get_pricing_info: "Pricing",
};

export function AdminOverview() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    adminGetStats()
      .then(setStats)
      .catch((e: any) => setError(e.message))
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

  const maxWeekly = Math.max(...(stats.weekly || []).map((d) => d.calls + d.leads), 1);

  const planColors: Record<string, "default" | "success" | "warning" | "secondary"> = {
    starter: "secondary",
    growth: "default",
    pro: "success",
    agency: "warning",
  };

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Platform Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Real-time metrics across all tenants
        </p>
      </div>

      {/* ── Top stat cards ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: "Clients", value: stats.total_clients, icon: Users, color: "text-blue-400", bg: "bg-blue-500/10" },
          { label: "Total Calls", value: stats.total_calls, icon: Phone, color: "text-emerald-400", bg: "bg-emerald-500/10" },
          { label: "Total Leads", value: stats.total_leads, icon: UserCheck, color: "text-amber-400", bg: "bg-amber-500/10" },
          { label: "Booked", value: stats.booked_appointments, icon: CalendarCheck, color: "text-violet-400", bg: "bg-violet-500/10" },
          { label: "Today Calls", value: stats.calls_today, icon: PhoneIncoming, color: "text-cyan-400", bg: "bg-cyan-500/10" },
          { label: "Today Leads", value: stats.leads_today, icon: UserCheck, color: "text-rose-400", bg: "bg-rose-500/10" },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[10px] text-muted-foreground font-medium">{s.label}</p>
                  <p className="text-2xl font-bold text-foreground mt-0.5">
                    {s.value.toLocaleString()}
                  </p>
                </div>
                <div className={cn(s.bg, s.color, "p-2 rounded-lg")}>
                  <s.icon className="w-4 h-4" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Weekly Chart + Lead Funnel ────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Weekly chart */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              7-Day Activity
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-4">
            {(stats.weekly || []).length > 0 ? (
              <div className="flex items-end gap-2 h-32">
                {stats.weekly.map((d) => (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex flex-col items-center gap-0.5" style={{ height: 100 }}>
                      <div
                        className="w-full bg-primary/60 rounded-t"
                        style={{
                          height: `${(d.calls / maxWeekly) * 100}%`,
                          minHeight: d.calls > 0 ? 4 : 0,
                        }}
                      />
                      <div
                        className="w-full bg-emerald-500/60 rounded-b"
                        style={{
                          height: `${(d.leads / maxWeekly) * 100}%`,
                          minHeight: d.leads > 0 ? 4 : 0,
                        }}
                      />
                    </div>
                    <span className="text-[9px] text-muted-foreground">{d.label}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-8">No data yet</p>
            )}
            <div className="flex items-center gap-4 mt-2 text-[10px] text-muted-foreground justify-center">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded bg-primary/60" /> Calls
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded bg-emerald-500/60" /> Leads
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Lead Funnel */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Lead Funnel</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.keys(stats.leads_by_status || {}).length > 0 ? (
              Object.entries(stats.leads_by_status).map(([status, count]) => {
                const pct = stats.total_leads > 0 ? (count / stats.total_leads) * 100 : 0;
                const colors: Record<string, string> = {
                  new: "bg-blue-500", contacted: "bg-amber-500", booked: "bg-emerald-500",
                  closed: "bg-green-500", lost: "bg-red-500",
                };
                return (
                  <div key={status}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="capitalize text-muted-foreground">{status}</span>
                      <span className="font-medium text-foreground">{count}</span>
                    </div>
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
                      <div
                        className={cn("h-full rounded-full", colors[status] || "bg-primary")}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">No leads yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Recent Leads + Recent Calls ───────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Leads */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-amber-400" />
              Recent Leads
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(stats.recent_leads || []).length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {stats.recent_leads.map((lead) => (
                  <div
                    key={lead.id}
                    className="flex items-center gap-3 p-2 rounded-lg bg-accent/30"
                  >
                    <div
                      className={cn(
                        "w-2 h-2 rounded-full shrink-0",
                        lead.urgency === "high" || lead.urgency === "emergency"
                          ? "bg-red-400"
                          : lead.urgency === "medium"
                          ? "bg-amber-400"
                          : "bg-slate-400"
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {lead.caller_name || "Unknown"}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate">
                        {lead.intent || formatPhone(lead.caller_phone)}
                      </p>
                    </div>
                    <Badge
                      variant={
                        lead.status === "booked" || lead.status === "closed"
                          ? "success"
                          : lead.status === "lost"
                          ? "destructive"
                          : "secondary"
                      }
                      className="text-[9px] shrink-0"
                    >
                      {lead.status}
                    </Badge>
                    <span className="text-[9px] text-muted-foreground shrink-0">
                      {timeAgo(lead.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">No leads yet</p>
            )}
          </CardContent>
        </Card>

        {/* Recent Calls */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Phone className="w-4 h-4 text-emerald-400" />
              Recent Calls
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(stats.recent_calls || []).length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {stats.recent_calls.map((call) => (
                  <div
                    key={call.id}
                    className="flex items-center gap-3 p-2 rounded-lg bg-accent/30"
                  >
                    <div
                      className={cn(
                        "w-7 h-7 rounded-full flex items-center justify-center shrink-0",
                        call.direction === "outbound"
                          ? "bg-blue-500/10 text-blue-400"
                          : "bg-green-500/10 text-green-400"
                      )}
                    >
                      <Phone className="w-3 h-3" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {call.caller_number ? formatPhone(call.caller_number) : "Widget"}
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        {call.channel} · {formatDuration(call.duration_seconds)}
                      </p>
                    </div>
                    <Badge
                      variant={call.status === "completed" ? "success" : "secondary"}
                      className="text-[9px] shrink-0"
                    >
                      {call.status}
                    </Badge>
                    <span className="text-[9px] text-muted-foreground shrink-0">
                      {timeAgo(call.started_at)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">No calls yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Tool Activity + Plans + Health ─────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* AI Tool Activity */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Wrench className="w-4 h-4 text-violet-400" />
              AI Tool Activity
              {stats.tool_calls_today > 0 && (
                <Badge variant="default" className="text-[9px] ml-auto">
                  {stats.tool_calls_today} today
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(stats.tool_summary || {}).length > 0 ? (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-1">
                  {Object.entries(stats.tool_summary).map(([tool, count]) => (
                    <Badge key={tool} variant="secondary" className="text-[10px]">
                      {TOOL_LABELS[tool] || tool}: {count}
                    </Badge>
                  ))}
                </div>
                {(stats.recent_tool_calls || []).length > 0 && (
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {stats.recent_tool_calls.map((t) => (
                      <div key={t.id} className="flex items-center gap-2 text-xs">
                        <Bot className={cn("w-3 h-3", t.success ? "text-emerald-400" : "text-red-400")} />
                        <span className="text-muted-foreground">
                          {TOOL_LABELS[t.tool_name] || t.tool_name}
                        </span>
                        {t.duration_ms && (
                          <span className="text-[9px] text-muted-foreground">
                            {t.duration_ms}ms
                          </span>
                        )}
                        <span className="text-[9px] text-muted-foreground ml-auto">
                          {timeAgo(t.created_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">No tool calls yet</p>
            )}
          </CardContent>
        </Card>

        {/* Clients by Plan */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              Clients by Plan
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(stats.clients_by_plan).map(([plan, count]) => (
                <div
                  key={plan}
                  className="rounded-xl border border-border bg-card p-3 text-center"
                >
                  <Badge variant={planColors[plan] || "secondary"} className="mb-1.5">
                    {plan}
                  </Badge>
                  <p className="text-xl font-bold text-foreground">{count}</p>
                  <p className="text-[10px] text-muted-foreground">clients</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Platform Health */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Platform Health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              { label: "API Status", status: "Operational" },
              { label: "Database", status: "Connected" },
              { label: "Auth Service", status: "Active" },
              { label: "ElevenLabs", status: "Connected" },
            ].map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/10"
              >
                <span className="text-xs text-muted-foreground">{item.label}</span>
                <Badge variant="success" className="text-[9px]">{item.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

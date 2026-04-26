"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Phone,
  Users,
  Clock,
  CalendarCheck,
  PhoneIncoming,
  PhoneOutgoing,
  Bot,
  Loader2,
  Wrench,
  AlertCircle,
  MessageSquareText,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatDuration, formatPhone, timeAgo } from "@/lib/utils";
import { getAnalytics, getWeeklyStats, getCalls, getLeads, getToolCallLogs } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

// ── Types ────────────────────────────────────────────────────────────────────

interface AnalyticsSummary {
  total_calls: number;
  completed_calls: number;
  calls_today: number;
  calls_this_week: number;
  missed_calls: number;
  avg_duration_seconds: number;
  total_leads: number;
  leads_today: number;
  booked_appointments: number;
  leads_by_status: Record<string, number>;
  avg_lead_score: number;
  conversion_rate: number;
  tool_calls_today: number;
}

interface WeeklyDay {
  date: string;
  label: string;
  calls: number;
  leads: number;
}

interface CallRecord {
  id: string;
  caller_number: string;
  direction: string;
  status: string;
  duration_seconds: number | null;
  started_at: string | null;
  created_at: string;
}

interface LeadRecord {
  id: string;
  caller_name: string;
  caller_phone: string;
  caller_email: string | null;
  intent: string | null;
  urgency: string;
  summary: string | null;
  services_requested: string[];
  status: string;
  lead_score: number;
  created_at: string;
}

interface ToolCallRecord {
  id: string;
  tool_name: string;
  parameters: Record<string, any>;
  result: Record<string, any>;
  success: boolean;
  duration_ms: number | null;
  created_at: string;
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  subValue,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  subValue?: string;
  icon: React.ElementType;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold text-foreground">{value}</p>
            {subValue && (
              <p className="text-[11px] text-muted-foreground">{subValue}</p>
            )}
          </div>
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10">
            <Icon className="w-5 h-5 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function MiniBarChart({ data, dataKey, color }: { data: WeeklyDay[]; dataKey: keyof WeeklyDay; color: string }) {
  const values = data.map((d) => Number(d[dataKey]) || 0);
  const max = Math.max(...values, 1);
  return (
    <div className="flex items-end gap-1 h-16">
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <div
            className="w-full rounded-sm transition-all"
            style={{
              height: `${(values[i] / max) * 100}%`,
              backgroundColor: color,
              minHeight: "2px",
            }}
          />
          <span className="text-[9px] text-muted-foreground">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

function LeadFunnelBar({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground capitalize">{label}</span>
        <span className="font-medium text-foreground">{count}</span>
      </div>
      <div className="h-2 bg-secondary rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${total > 0 ? (count / total) * 100 : 0}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

const FUNNEL_COLORS: Record<string, string> = {
  new: "hsl(243, 75%, 59%)",
  contacted: "hsl(200, 70%, 55%)",
  booked: "hsl(142, 76%, 36%)",
  closed: "hsl(38, 92%, 50%)",
  lost: "hsl(0, 62%, 50%)",
};

const TOOL_LABELS: Record<string, string> = {
  capture_lead: "Lead Captured",
  book_appointment: "Appointment Booked",
  send_confirmation_sms: "SMS Sent",
  check_availability: "Availability Checked",
  get_pricing_info: "Pricing Requested",
};

// ── Main Page ────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<AnalyticsSummary | null>(null);
  const [weekly, setWeekly] = useState<WeeklyDay[]>([]);
  const [recentCalls, setRecentCalls] = useState<CallRecord[]>([]);
  const [recentLeads, setRecentLeads] = useState<LeadRecord[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([]);
  const [toolSummary, setToolSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const [analyticsRes, weeklyRes, callsRes, leadsRes, toolsRes] = await Promise.all([
          getAnalytics(),
          getWeeklyStats(),
          getCalls(undefined, 6, 0),
          getLeads({ limit: 6 }),
          getToolCallLogs({ limit: 10 }),
        ]);
        setStats(analyticsRes);
        setWeekly(weeklyRes.days || []);
        setRecentCalls(callsRes.calls || []);
        setRecentLeads(leadsRes.leads || []);
        setToolCalls(toolsRes.logs || []);
        setToolSummary(toolsRes.tool_summary || {});
      } catch (e: any) {
        setError(e.message || "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-3">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
    );
  }

  if (!stats) return null;

  const funnelOrder = ["new", "contacted", "booked", "closed", "lost"];
  const funnelTotal = Object.values(stats.leads_by_status).reduce((a, b) => a + b, 0) || 1;

  // Weekly derived stats
  const weeklyCallsTotal = weekly.reduce((a, d) => a + d.calls, 0);
  const peakDay = weekly.length > 0
    ? weekly.reduce((best, d) => (d.calls > best.calls ? d : best), weekly[0])
    : null;
  const avgPerDay = weekly.length > 0 ? (weeklyCallsTotal / weekly.length).toFixed(1) : "0";
  const answerRate = stats.total_calls > 0
    ? ((stats.completed_calls / stats.total_calls) * 100).toFixed(1)
    : "0";

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            AI Agent Overview
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-medium text-emerald-400">Agent Online</span>
          </div>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Calls"
          value={stats.total_calls.toLocaleString()}
          subValue={`${stats.calls_today} today · ${stats.calls_this_week} this week`}
          icon={Phone}
        />
        <StatCard
          label="Leads Captured"
          value={stats.total_leads}
          subValue={`${stats.leads_today} today · ${stats.conversion_rate}% conversion`}
          icon={Users}
        />
        <StatCard
          label="Booked Appointments"
          value={stats.booked_appointments}
          subValue={`Avg lead score: ${Math.round(stats.avg_lead_score * 100)}%`}
          icon={CalendarCheck}
        />
        <StatCard
          label="Avg Call Duration"
          value={formatDuration(stats.avg_duration_seconds)}
          subValue={`${stats.missed_calls} missed calls`}
          icon={Clock}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Weekly call volume */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Call Volume — This Week</CardTitle>
              <div className="flex items-center gap-3 text-[11px]">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-primary" /> Calls
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" /> Leads
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {weekly.length > 0 ? (
                <MiniBarChart data={weekly} dataKey="calls" color="hsl(243, 75%, 59%)" />
              ) : (
                <div className="h-16 flex items-center justify-center text-xs text-muted-foreground">
                  No call data this week
                </div>
              )}
              <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border">
                <div>
                  <p className="text-[11px] text-muted-foreground">Peak Day</p>
                  <p className="text-sm font-semibold">{peakDay?.label || "—"}</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground">Avg / Day</p>
                  <p className="text-sm font-semibold">{avgPerDay} calls</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground">Answer Rate</p>
                  <p className="text-sm font-semibold text-emerald-400">{answerRate}%</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Lead Funnel */}
        <Card>
          <CardHeader>
            <CardTitle>Lead Funnel</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {funnelOrder.map((status) => (
                <LeadFunnelBar
                  key={status}
                  label={status}
                  count={stats.leads_by_status[status] || 0}
                  total={funnelTotal}
                  color={FUNNEL_COLORS[status] || "hsl(243, 75%, 59%)"}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Calls + Recent Leads */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Calls */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Calls</CardTitle>
          </CardHeader>
          <CardContent>
            {recentCalls.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No calls yet</p>
            ) : (
              <div className="space-y-1">
                {recentCalls.map((call) => (
                  <div
                    key={call.id}
                    className="flex items-center gap-3 py-2.5 px-2 rounded-lg hover:bg-accent/50 transition-colors"
                  >
                    <div
                      className={cn(
                        "flex items-center justify-center w-8 h-8 rounded-full shrink-0",
                        call.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : call.status === "no_answer" || call.status === "missed"
                          ? "bg-amber-500/10 text-amber-400"
                          : "bg-red-500/10 text-red-400"
                      )}
                    >
                      {call.direction === "inbound" ? (
                        <PhoneIncoming className="w-3.5 h-3.5" />
                      ) : (
                        <PhoneOutgoing className="w-3.5 h-3.5" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {formatPhone(call.caller_number)}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {timeAgo(call.started_at || call.created_at)} · {formatDuration(call.duration_seconds)}
                      </p>
                    </div>
                    <Badge
                      variant={
                        call.status === "completed"
                          ? "success"
                          : call.status === "no_answer" || call.status === "missed"
                          ? "warning"
                          : "destructive"
                      }
                    >
                      {call.status.replace("_", " ")}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Leads */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Leads</CardTitle>
          </CardHeader>
          <CardContent>
            {recentLeads.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No leads yet</p>
            ) : (
              <div className="space-y-1">
                {recentLeads.map((lead) => (
                  <div
                    key={lead.id}
                    className="flex items-center gap-3 py-2.5 px-2 rounded-lg hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
                      {(lead.caller_name || "?")
                        .split(" ")
                        .map((n: string) => n[0])
                        .join("")}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {lead.caller_name || "Unknown"}
                      </p>
                      <p className="text-[11px] text-muted-foreground truncate">
                        {lead.summary || lead.intent || "—"}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <Badge
                        variant={
                          lead.urgency === "emergency" || lead.urgency === "high"
                            ? "destructive"
                            : lead.status === "booked"
                            ? "success"
                            : "secondary"
                        }
                      >
                        {lead.status}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        {Math.round(lead.lead_score * 100)}% score
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* AI Tool Activity */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Wrench className="w-4 h-4" />
              AI Tool Activity
            </CardTitle>
            <span className="text-[11px] text-muted-foreground">
              {stats.tool_calls_today} tool calls today
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {/* Summary badges */}
          <div className="flex flex-wrap gap-2 mb-4">
            {Object.entries(toolSummary).map(([name, count]) => (
              <Badge key={name} variant="secondary" className="text-xs">
                {TOOL_LABELS[name] || name}: {count}
              </Badge>
            ))}
            {Object.keys(toolSummary).length === 0 && (
              <span className="text-xs text-muted-foreground">No tool calls yet</span>
            )}
          </div>

          {/* Recent tool calls */}
          {toolCalls.length > 0 && (
            <div className="space-y-1">
              {toolCalls.slice(0, 5).map((tc) => (
                <div
                  key={tc.id}
                  className="flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div className={cn(
                    "flex items-center justify-center w-7 h-7 rounded-full shrink-0",
                    tc.success ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                  )}>
                    <Wrench className="w-3 h-3" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground">
                      {TOOL_LABELS[tc.tool_name] || tc.tool_name}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {tc.parameters?.name && `${tc.parameters.name} · `}
                      {tc.parameters?.email || tc.parameters?.phone || tc.parameters?.service || ""}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-[10px] text-muted-foreground">{timeAgo(tc.created_at)}</p>
                    {tc.duration_ms && (
                      <p className="text-[9px] text-muted-foreground">{tc.duration_ms}ms</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Conversation Summaries */}
      <ConversationSummariesCard leads={recentLeads} />

      {/* AI Agent Status Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-foreground">AI Agent</span>
                <Badge variant="success">active</Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Omniweb Conversational AI · 5 tools connected
              </p>
            </div>
            <div className="hidden md:flex items-center gap-6 text-center">
              <div>
                <p className="text-lg font-bold text-foreground">{answerRate}%</p>
                <p className="text-[10px] text-muted-foreground">Answer Rate</p>
              </div>
              <div className="w-px h-8 bg-border" />
              <div>
                <p className="text-lg font-bold text-foreground">{stats.conversion_rate}%</p>
                <p className="text-[10px] text-muted-foreground">Lead Conv.</p>
              </div>
              <div className="w-px h-8 bg-border" />
              <div>
                <p className="text-lg font-bold text-foreground">{stats.booked_appointments}</p>
                <p className="text-[10px] text-muted-foreground">Booked</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Conversation Summaries Card ───────────────────────────────────────────────

function ConversationSummariesCard({ leads }: { leads: LeadRecord[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggle = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  const summaryLeads = leads.filter((l) => l.summary && l.summary.trim().length > 0);

  const urgencyColor: Record<string, string> = {
    emergency: "text-red-400 bg-red-500/10 border-red-500/20",
    high: "text-orange-400 bg-orange-500/10 border-orange-500/20",
    medium: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
    low: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <MessageSquareText className="w-4 h-4 text-primary" />
            Conversation Summaries
          </CardTitle>
          <span className="text-[11px] text-muted-foreground">
            {summaryLeads.length} recent {summaryLeads.length === 1 ? "summary" : "summaries"}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {summaryLeads.length === 0 ? (
          <div className="py-8 text-center">
            <MessageSquareText className="w-8 h-8 mx-auto mb-2 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              Conversation summaries will appear here after your AI agent completes sessions.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {summaryLeads.map((lead) => {
              const isExpanded = expandedId === lead.id;
              const initials = (lead.caller_name || "?")
                .split(" ")
                .map((n: string) => n[0])
                .join("")
                .toUpperCase()
                .slice(0, 2);
              const urg = lead.urgency?.toLowerCase() || "low";
              const urgClass = urgencyColor[urg] || urgencyColor.low;

              return (
                <div
                  key={lead.id}
                  className="rounded-xl border border-border overflow-hidden transition-all"
                >
                  {/* Row header — always visible */}
                  <button
                    className="w-full flex items-center gap-3 p-3 hover:bg-accent/40 transition-colors text-left"
                    onClick={() => toggle(lead.id)}
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
                      {initials}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-foreground truncate">
                          {lead.caller_name || "Unknown Visitor"}
                        </p>
                        <span className={cn(
                          "hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border shrink-0",
                          urgClass
                        )}>
                          {urg}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                        {isExpanded ? "Click to collapse" : lead.summary?.slice(0, 90) + (lead.summary!.length > 90 ? "…" : "")}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] text-muted-foreground">
                        {timeAgo(lead.created_at)}
                      </span>
                      {isExpanded
                        ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                        : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
                    </div>
                  </button>

                  {/* Expanded summary body */}
                  {isExpanded && (
                    <div className="border-t border-border px-4 py-3 bg-muted/30 space-y-3">
                      <p className="text-sm text-foreground leading-relaxed">{lead.summary}</p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        {lead.intent && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/10 border border-primary/20 text-xs text-primary font-medium">
                            Intent: {lead.intent}
                          </span>
                        )}
                        {lead.services_requested?.map((s: string) => (
                          <span key={s} className="inline-flex items-center px-2.5 py-1 rounded-full bg-secondary border border-border text-xs text-muted-foreground">
                            {s}
                          </span>
                        ))}
                        <span className={cn(
                          "ml-auto inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border",
                          lead.status === "booked"
                            ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                            : "text-muted-foreground bg-secondary border-border"
                        )}>
                          {lead.status}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

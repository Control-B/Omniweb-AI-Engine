"use client";

import {
  Phone,
  Users,
  Clock,
  TrendingUp,
  PhoneIncoming,
  PhoneOutgoing,
  PhoneMissed,
  ArrowUpRight,
  ArrowDownRight,
  Bot,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatDuration, formatPhone, timeAgo } from "@/lib/utils";
import {
  MOCK_ANALYTICS,
  MOCK_CALLS,
  MOCK_LEADS,
  MOCK_WEEKLY_CALLS,
  MOCK_HOURLY_CALLS,
} from "@/lib/mock-data";

function StatCard({
  label,
  value,
  subValue,
  icon: Icon,
  trend,
  trendUp,
}: {
  label: string;
  value: string | number;
  subValue?: string;
  icon: React.ElementType;
  trend?: string;
  trendUp?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">{label}</p>
            <div className="flex items-baseline gap-2">
              <p className="text-2xl font-bold text-foreground">{value}</p>
              {trend && (
                <span
                  className={cn(
                    "flex items-center text-[11px] font-medium",
                    trendUp ? "text-emerald-400" : "text-red-400"
                  )}
                >
                  {trendUp ? (
                    <ArrowUpRight className="w-3 h-3" />
                  ) : (
                    <ArrowDownRight className="w-3 h-3" />
                  )}
                  {trend}
                </span>
              )}
            </div>
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

function MiniBarChart({ data, dataKey, color }: { data: { [k: string]: any }[]; dataKey: string; color: string }) {
  const max = Math.max(...data.map((d) => d[dataKey]));
  return (
    <div className="flex items-end gap-1 h-16">
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <div
            className="w-full rounded-sm transition-all"
            style={{
              height: `${(d[dataKey] / max) * 100}%`,
              backgroundColor: color,
              minHeight: "2px",
            }}
          />
          <span className="text-[9px] text-muted-foreground">{d.day || d.hour}</span>
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
          style={{ width: `${(count / total) * 100}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export function DashboardPage() {
  const stats = MOCK_ANALYTICS;

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Bob&apos;s Plumbing — AI Agent Overview
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
          trend="+12.5%"
          trendUp
        />
        <StatCard
          label="Leads Captured"
          value={stats.total_leads}
          subValue={`${stats.conversion_rate}% conversion rate`}
          icon={Users}
          trend="+8.2%"
          trendUp
        />
        <StatCard
          label="Avg Call Duration"
          value={formatDuration(stats.avg_duration_seconds)}
          subValue="Across all completed calls"
          icon={Clock}
          trend="+15s"
          trendUp
        />
        <StatCard
          label="Missed Calls"
          value={stats.missed_calls}
          subValue="Auto follow-up SMS sent"
          icon={PhoneMissed}
          trend="-4.1%"
          trendUp
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
              <MiniBarChart data={MOCK_WEEKLY_CALLS} dataKey="calls" color="hsl(243, 75%, 59%)" />
              <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border">
                <div>
                  <p className="text-[11px] text-muted-foreground">Peak Day</p>
                  <p className="text-sm font-semibold">Thursday</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground">Avg / Day</p>
                  <p className="text-sm font-semibold">24.6 calls</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground">Answer Rate</p>
                  <p className="text-sm font-semibold text-emerald-400">94.2%</p>
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
              <LeadFunnelBar label="new" count={47} total={312} color="hsl(243, 75%, 59%)" />
              <LeadFunnelBar label="contacted" count={89} total={312} color="hsl(200, 70%, 55%)" />
              <LeadFunnelBar label="booked" count={134} total={312} color="hsl(142, 76%, 36%)" />
              <LeadFunnelBar label="closed" count={28} total={312} color="hsl(38, 92%, 50%)" />
              <LeadFunnelBar label="lost" count={14} total={312} color="hsl(0, 62%, 50%)" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Calls + Recent Leads */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Calls */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent Calls</CardTitle>
              <button className="text-[11px] text-primary hover:underline">View all →</button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {MOCK_CALLS.slice(0, 6).map((call) => (
                <div
                  key={call.id}
                  className="flex items-center gap-3 py-2.5 px-2 rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div
                    className={cn(
                      "flex items-center justify-center w-8 h-8 rounded-full shrink-0",
                      call.status === "completed"
                        ? "bg-emerald-500/10 text-emerald-400"
                        : call.status === "no_answer"
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
                      {timeAgo(call.started_at)} · {formatDuration(call.duration_seconds)}
                    </p>
                  </div>
                  <Badge
                    variant={
                      call.status === "completed"
                        ? "success"
                        : call.status === "no_answer"
                        ? "warning"
                        : "destructive"
                    }
                  >
                    {call.status.replace("_", " ")}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Recent Leads */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent Leads</CardTitle>
              <button className="text-[11px] text-primary hover:underline">View all →</button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {MOCK_LEADS.map((lead) => (
                <div
                  key={lead.id}
                  className="flex items-center gap-3 py-2.5 px-2 rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
                    {lead.caller_name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {lead.caller_name}
                    </p>
                    <p className="text-[11px] text-muted-foreground truncate">
                      {lead.summary}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <Badge
                      variant={
                        lead.urgency === "emergency"
                          ? "destructive"
                          : lead.urgency === "high"
                          ? "warning"
                          : "secondary"
                      }
                    >
                      {lead.urgency}
                    </Badge>
                    <span className="text-[10px] text-muted-foreground">
                      {Math.round(lead.lead_score * 100)}% score
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* AI Agent Status Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-foreground">Aria</span>
                <Badge variant="success">active</Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Deepgram Nova-3 STT · GPT-4o · ElevenLabs Rachel · 3.2s avg response time
              </p>
            </div>
            <div className="hidden md:flex items-center gap-6 text-center">
              <div>
                <p className="text-lg font-bold text-foreground">94.2%</p>
                <p className="text-[10px] text-muted-foreground">Answer Rate</p>
              </div>
              <div className="w-px h-8 bg-border" />
              <div>
                <p className="text-lg font-bold text-foreground">4.8/5</p>
                <p className="text-[10px] text-muted-foreground">Sentiment</p>
              </div>
              <div className="w-px h-8 bg-border" />
              <div>
                <p className="text-lg font-bold text-foreground">28.6%</p>
                <p className="text-[10px] text-muted-foreground">Lead Conv.</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

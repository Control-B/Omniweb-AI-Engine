"use client";

import { useState } from "react";
import { Search, Mail, Phone, ExternalLink, ChevronDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn, formatPhone, timeAgo } from "@/lib/utils";
import { MOCK_LEADS, type LeadRecord } from "@/lib/mock-data";

const STATUS_OPTIONS = ["new", "contacted", "booked", "closed", "lost"] as const;
const URGENCY_COLOR: Record<string, string> = {
  emergency: "bg-red-500",
  high: "bg-amber-500",
  medium: "bg-blue-500",
  low: "bg-slate-400",
};

function LeadScoreRing({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "text-emerald-400" : pct >= 50 ? "text-amber-400" : "text-red-400";
  return (
    <div className={cn("text-base font-bold", color)}>
      {pct}
    </div>
  );
}

export function LeadsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedLead, setSelectedLead] = useState<LeadRecord | null>(null);

  const filtered = MOCK_LEADS.filter((l) => {
    if (statusFilter !== "all" && l.status !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        l.caller_name.toLowerCase().includes(q) ||
        l.caller_phone.includes(q) ||
        l.intent.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="p-6 space-y-4 max-w-[1400px]">
      <div>
        <h1 className="text-xl font-bold text-foreground">Leads</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          AI-extracted leads from phone conversations
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by name, phone, or intent..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex items-center rounded-lg border border-border overflow-hidden">
          {["all", ...STATUS_OPTIONS].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium transition-colors capitalize",
                statusFilter === s
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Leads List */}
        <Card className="lg:col-span-3">
          <CardContent className="p-0">
            <div className="divide-y divide-border">
              {filtered.map((lead) => (
                <button
                  key={lead.id}
                  onClick={() => setSelectedLead(lead)}
                  className={cn(
                    "flex items-center gap-3 w-full px-5 py-4 text-left transition-colors hover:bg-accent/50",
                    selectedLead?.id === lead.id && "bg-accent/50"
                  )}
                >
                  {/* Urgency dot */}
                  <div className={cn("w-2 h-2 rounded-full shrink-0", URGENCY_COLOR[lead.urgency])} />

                  {/* Avatar */}
                  <div className="flex items-center justify-center w-9 h-9 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
                    {lead.caller_name.split(" ").map((n) => n[0]).join("")}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground">{lead.caller_name}</p>
                      {lead.follow_up_sent && (
                        <Mail className="w-3 h-3 text-muted-foreground" />
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground truncate">
                      {lead.intent} · {lead.services_requested.slice(0, 2).join(", ")} · {timeAgo(lead.created_at)}
                    </p>
                  </div>

                  {/* Score + Status */}
                  <div className="flex items-center gap-3 shrink-0">
                    <LeadScoreRing score={lead.lead_score} />
                    <Badge
                      variant={
                        lead.status === "booked"
                          ? "success"
                          : lead.status === "new"
                          ? "default"
                          : lead.status === "contacted"
                          ? "warning"
                          : lead.status === "lost"
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {lead.status}
                    </Badge>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Lead Detail */}
        <Card className="lg:col-span-2">
          {selectedLead ? (
            <>
              <CardHeader>
                <CardTitle>Lead Detail</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Contact info */}
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center text-lg">
                    {selectedLead.caller_name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div>
                    <p className="text-base font-semibold text-foreground">{selectedLead.caller_name}</p>
                    <p className="text-xs text-muted-foreground">{formatPhone(selectedLead.caller_phone)}</p>
                    {selectedLead.caller_email && (
                      <p className="text-xs text-muted-foreground">{selectedLead.caller_email}</p>
                    )}
                  </div>
                </div>

                {/* Quick stats */}
                <div className="grid grid-cols-3 gap-3 p-3 rounded-lg bg-accent/50">
                  <div className="text-center">
                    <p className="text-[10px] text-muted-foreground">Score</p>
                    <p className="text-lg font-bold text-foreground">{Math.round(selectedLead.lead_score * 100)}%</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] text-muted-foreground">Urgency</p>
                    <Badge
                      variant={
                        selectedLead.urgency === "emergency"
                          ? "destructive"
                          : selectedLead.urgency === "high"
                          ? "warning"
                          : "secondary"
                      }
                    >
                      {selectedLead.urgency}
                    </Badge>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] text-muted-foreground">Status</p>
                    <Badge variant="success">{selectedLead.status}</Badge>
                  </div>
                </div>

                {/* Summary */}
                <div>
                  <p className="text-xs font-semibold text-foreground mb-1">AI Summary</p>
                  <p className="text-sm text-muted-foreground leading-relaxed">{selectedLead.summary}</p>
                </div>

                {/* Services */}
                <div>
                  <p className="text-xs font-semibold text-foreground mb-2">Services Requested</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedLead.services_requested.map((s) => (
                      <Badge key={s} variant="outline">{s}</Badge>
                    ))}
                  </div>
                </div>

                {/* Intent */}
                <div>
                  <p className="text-xs font-semibold text-foreground mb-1">Intent</p>
                  <p className="text-sm text-muted-foreground capitalize">{selectedLead.intent}</p>
                </div>

                {/* Actions */}
                <div className="border-t border-border pt-3 flex gap-2">
                  <Button size="sm" variant="default" className="flex-1">
                    <Phone className="w-3.5 h-3.5" />
                    Call Back
                  </Button>
                  <Button size="sm" variant="outline" className="flex-1">
                    <Mail className="w-3.5 h-3.5" />
                    Send SMS
                  </Button>
                </div>
              </CardContent>
            </>
          ) : (
            <CardContent className="flex items-center justify-center h-64">
              <div className="text-center">
                <ExternalLink className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Select a lead to view details</p>
              </div>
            </CardContent>
          )}
        </Card>
      </div>
    </div>
  );
}

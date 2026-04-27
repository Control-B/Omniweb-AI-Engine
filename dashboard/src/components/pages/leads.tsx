"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, Loader2, AlertCircle, Mail, Phone as PhoneIcon, MapPin, Star, ArrowUpDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn, formatPhone, timeAgo } from "@/lib/utils";
import { getLeads, getLead, updateLeadStatus } from "@/lib/api";

interface LeadRecord {
  id: string;
  call_id: string | null;
  caller_name: string;
  caller_phone: string;
  caller_email: string | null;
  intent: string | null;
  urgency: string;
  summary: string | null;
  services_requested: string[];
  status: string;
  lead_score: number;
  follow_up_sent: boolean;
  created_at: string;
}

interface LeadDetail extends LeadRecord {
  client_id: string;
  status_notes: string | null;
  follow_up_at: string | null;
}

const STATUS_OPTIONS = ["all", "new", "contacted", "booked", "closed", "lost"];

export function LeadsPage() {
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<LeadDetail | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const loadLeads = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getLeads({
        status: statusFilter === "all" ? undefined : statusFilter,
        search: search || undefined,
        limit: 100,
      });
      setLeads(res.leads || []);
      setTotal(res.total || 0);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  // Load detail when selection changes
  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    (async () => {
      try {
        setDetailLoading(true);
        const res = await getLead(selectedId);
        setDetail(res);
      } catch {
        setDetail(null);
      } finally {
        setDetailLoading(false);
      }
    })();
  }, [selectedId]);

  async function handleStatusChange(newStatus: string) {
    if (!selectedId || !detail) return;
    try {
      setUpdatingStatus(true);
      await updateLeadStatus(selectedId, newStatus);
      setDetail({ ...detail, status: newStatus });
      // Refresh list
      setLeads((prev) =>
        prev.map((l) => (l.id === selectedId ? { ...l, status: newStatus } : l))
      );
    } catch {
      // ignore
    } finally {
      setUpdatingStatus(false);
    }
  }

  const filteredLeads = leads;

  return (
    <div className="flex h-full">
      {/* Left panel — lead list */}
      <div className="w-full lg:w-3/5 border-r border-border flex flex-col">
        {/* Search + filters */}
        <div className="p-4 border-b border-border space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search by name, phone, or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex gap-1 flex-wrap">
            {STATUS_OPTIONS.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={statusFilter === s ? "default" : "ghost"}
                className="h-7 text-xs capitalize"
                onClick={() => { setStatusFilter(s); setSelectedId(null); }}
              >
                {s}
              </Button>
            ))}
            <span className="ml-auto text-xs text-muted-foreground self-center">
              {total} lead{total !== 1 ? "s" : ""}
            </span>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center py-12 gap-2">
              <AlertCircle className="w-6 h-6 text-red-400" />
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          ) : filteredLeads.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-muted-foreground">No leads found</p>
            </div>
          ) : (
            filteredLeads.map((lead) => (
              <div
                key={lead.id}
                onClick={() => setSelectedId(lead.id)}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 cursor-pointer border-b border-border hover:bg-accent/50 transition-colors",
                  selectedId === lead.id && "bg-accent"
                )}
              >
                {/* Urgency dot */}
                <div
                  className={cn(
                    "w-2 h-2 rounded-full shrink-0",
                    lead.urgency === "emergency" || lead.urgency === "high"
                      ? "bg-red-400"
                      : lead.urgency === "medium"
                      ? "bg-cyan-400"
                      : "bg-slate-400"
                  )}
                />

                {/* Avatar */}
                <div className="flex items-center justify-center w-9 h-9 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
                  {(lead.caller_name || "?")
                    .split(" ")
                    .map((n: string) => n[0])
                    .join("")}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-foreground truncate">
                      {lead.caller_name || "Unknown"}
                    </p>
                    {lead.caller_email && (
                      <Mail className="w-3 h-3 text-muted-foreground shrink-0" />
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground truncate">
                    {lead.intent || lead.summary || formatPhone(lead.caller_phone)}
                  </p>
                  {lead.services_requested?.length > 0 && (
                    <div className="flex gap-1 mt-1">
                      {lead.services_requested.slice(0, 2).map((s, i) => (
                        <Badge key={i} variant="secondary" className="text-[9px] h-4 px-1">
                          {s}
                        </Badge>
                      ))}
                      {lead.services_requested.length > 2 && (
                        <span className="text-[9px] text-muted-foreground">
                          +{lead.services_requested.length - 2}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Right side */}
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <Badge
                    variant={
                      lead.status === "booked" || lead.status === "closed"
                        ? "success"
                        : lead.status === "lost"
                        ? "destructive"
                        : "secondary"
                    }
                    className="text-[10px]"
                  >
                    {lead.status}
                  </Badge>
                  <div className="flex items-center gap-1">
                    <div
                      className="w-6 h-6 rounded-full border-2 flex items-center justify-center"
                      style={{
                        borderColor: `hsl(${lead.lead_score * 120}, 70%, 50%)`,
                      }}
                    >
                      <span className="text-[8px] font-bold">
                        {Math.round(lead.lead_score * 100)}
                      </span>
                    </div>
                  </div>
                  <span className="text-[9px] text-muted-foreground">
                    {timeAgo(lead.created_at)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right panel — lead detail */}
      <div className="hidden lg:flex lg:w-2/5 flex-col overflow-y-auto">
        {detailLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : !detail ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground">Select a lead to view details</p>
          </div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-start gap-4">
              <div className="flex items-center justify-center w-14 h-14 rounded-full bg-primary/10 text-primary text-lg font-bold shrink-0">
                {(detail.caller_name || "?")
                  .split(" ")
                  .map((n: string) => n[0])
                  .join("")}
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  {detail.caller_name || "Unknown"}
                </h2>
                <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                  {detail.caller_phone && (
                    <span className="flex items-center gap-1">
                      <PhoneIcon className="w-3 h-3" />
                      {formatPhone(detail.caller_phone)}
                    </span>
                  )}
                  {detail.caller_email && (
                    <span className="flex items-center gap-1">
                      <Mail className="w-3 h-3" />
                      {detail.caller_email}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-3">
              <Card>
                <CardContent className="p-3 text-center">
                  <p className="text-[10px] text-muted-foreground">Score</p>
                  <p className="text-xl font-bold" style={{ color: `hsl(${detail.lead_score * 120}, 70%, 50%)` }}>
                    {Math.round(detail.lead_score * 100)}%
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <p className="text-[10px] text-muted-foreground">Urgency</p>
                  <p className="text-sm font-semibold capitalize">{detail.urgency}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <p className="text-[10px] text-muted-foreground">Status</p>
                  <p className="text-sm font-semibold capitalize">{detail.status}</p>
                </CardContent>
              </Card>
            </div>

            {/* Status update buttons */}
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">Update Status</p>
              <div className="flex flex-wrap gap-1">
                {["new", "contacted", "booked", "closed", "lost"].map((s) => (
                  <Button
                    key={s}
                    size="sm"
                    variant={detail.status === s ? "default" : "outline"}
                    className="h-7 text-xs capitalize"
                    disabled={updatingStatus || detail.status === s}
                    onClick={() => handleStatusChange(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </div>

            {/* AI Summary */}
            {detail.summary && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">AI Summary</p>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-sm text-foreground leading-relaxed">{detail.summary}</p>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Services Requested */}
            {detail.services_requested?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Services Interested</p>
                <div className="flex flex-wrap gap-1">
                  {detail.services_requested.map((s, i) => (
                    <Badge key={i} variant="secondary">{s}</Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Intent */}
            {detail.intent && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Intent</p>
                <p className="text-sm text-foreground">{detail.intent}</p>
              </div>
            )}

            {/* Follow-up */}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {detail.follow_up_sent ? (
                <Badge variant="success" className="text-[10px]">Follow-up sent</Badge>
              ) : (
                <Badge variant="secondary" className="text-[10px]">No follow-up yet</Badge>
              )}
              <span>·</span>
              <span>Created {timeAgo(detail.created_at)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

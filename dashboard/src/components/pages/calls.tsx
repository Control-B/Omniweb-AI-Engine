"use client";

import { useState } from "react";
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  Search,
  Filter,
  X,
  Play,
  MessageSquare,
  ExternalLink,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn, formatDuration, formatPhone, timeAgo } from "@/lib/utils";
import { MOCK_CALLS, type CallRecord } from "@/lib/mock-data";

function CallStatusBadge({ status }: { status: string }) {
  const v =
    status === "completed"
      ? "success"
      : status === "in_progress"
      ? "default"
      : status === "no_answer" || status === "missed"
      ? "warning"
      : "destructive";
  return <Badge variant={v as any}>{status.replace(/_/g, " ")}</Badge>;
}

function TranscriptView({ transcript }: { transcript: CallRecord["transcript"] }) {
  if (!transcript?.length) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        No transcript available for this call
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
      {transcript.map((turn, i) => (
        <div
          key={i}
          className={cn(
            "flex gap-3",
            turn.speaker === "agent" ? "flex-row" : "flex-row-reverse"
          )}
        >
          <div
            className={cn(
              "w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0",
              turn.speaker === "agent"
                ? "bg-primary/20 text-primary"
                : "bg-blue-500/20 text-blue-400"
            )}
          >
            {turn.speaker === "agent" ? "AI" : "C"}
          </div>
          <div
            className={cn(
              "max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm",
              turn.speaker === "agent"
                ? "bg-accent text-foreground rounded-tl-sm"
                : "bg-primary/10 text-foreground rounded-tr-sm"
            )}
          >
            {turn.text}
          </div>
        </div>
      ))}
    </div>
  );
}

export function CallsPage() {
  const [search, setSearch] = useState("");
  const [selectedCall, setSelectedCall] = useState<CallRecord | null>(null);
  const [dirFilter, setDirFilter] = useState<"all" | "inbound" | "outbound">("all");

  const filtered = MOCK_CALLS.filter((c) => {
    if (dirFilter !== "all" && c.direction !== dirFilter) return false;
    if (search && !c.caller_number.includes(search)) return false;
    return true;
  });

  return (
    <div className="p-6 space-y-4 max-w-[1400px]">
      <div>
        <h1 className="text-xl font-bold text-foreground">Calls</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          View all inbound and outbound call history
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by phone number..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex items-center rounded-lg border border-border overflow-hidden">
          {(["all", "inbound", "outbound"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setDirFilter(f)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium transition-colors capitalize",
                dirFilter === f
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Call List */}
        <Card className="lg:col-span-3">
          <CardContent className="p-0">
            <div className="divide-y divide-border">
              {filtered.map((call) => (
                <button
                  key={call.id}
                  onClick={() => setSelectedCall(call)}
                  className={cn(
                    "flex items-center gap-3 w-full px-5 py-3.5 text-left transition-colors hover:bg-accent/50",
                    selectedCall?.id === call.id && "bg-accent/50"
                  )}
                >
                  <div
                    className={cn(
                      "flex items-center justify-center w-9 h-9 rounded-full shrink-0",
                      call.status === "completed"
                        ? "bg-emerald-500/10 text-emerald-400"
                        : call.status === "no_answer"
                        ? "bg-amber-500/10 text-amber-400"
                        : call.status === "failed"
                        ? "bg-red-500/10 text-red-400"
                        : "bg-blue-500/10 text-blue-400"
                    )}
                  >
                    {call.direction === "inbound" ? (
                      <PhoneIncoming className="w-4 h-4" />
                    ) : (
                      <PhoneOutgoing className="w-4 h-4" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground">
                        {formatPhone(call.caller_number)}
                      </p>
                      {call.lead_id && (
                        <Badge variant="default" className="text-[9px]">
                          lead
                        </Badge>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {timeAgo(call.started_at)} · {formatDuration(call.duration_seconds)} ·{" "}
                      {call.direction}
                    </p>
                  </div>
                  <CallStatusBadge status={call.status} />
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Call Detail */}
        <Card className="lg:col-span-2">
          {selectedCall ? (
            <>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Call Detail</CardTitle>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setSelectedCall(null)}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-[11px] text-muted-foreground">Number</p>
                    <p className="text-sm font-medium">
                      {formatPhone(selectedCall.caller_number)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground">Duration</p>
                    <p className="text-sm font-medium">
                      {formatDuration(selectedCall.duration_seconds)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground">Direction</p>
                    <p className="text-sm font-medium capitalize">
                      {selectedCall.direction}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground">Status</p>
                    <CallStatusBadge status={selectedCall.status} />
                  </div>
                </div>

                <div className="border-t border-border pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <MessageSquare className="w-4 h-4 text-muted-foreground" />
                    <p className="text-xs font-semibold text-foreground">Transcript</p>
                  </div>
                  <TranscriptView transcript={selectedCall.transcript} />
                </div>

                {selectedCall.lead_id && (
                  <div className="border-t border-border pt-3">
                    <button className="flex items-center gap-1.5 text-xs text-primary hover:underline">
                      <ExternalLink className="w-3 h-3" />
                      View extracted lead →
                    </button>
                  </div>
                )}
              </CardContent>
            </>
          ) : (
            <CardContent className="flex items-center justify-center h-64">
              <div className="text-center">
                <Phone className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  Select a call to view details
                </p>
              </div>
            </CardContent>
          )}
        </Card>
      </div>
    </div>
  );
}

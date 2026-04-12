"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  Loader2,
  AlertCircle,
  RefreshCw,
  MessageSquare,
  Clock,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDuration, formatPhone, timeAgo } from "@/lib/utils";
import { getCalls, getCall, syncCalls } from "@/lib/api";

interface CallRecord {
  id: string;
  caller_number: string;
  direction: string;
  channel: string;
  status: string;
  duration_seconds: number | null;
  started_at: string | null;
  ended_at: string | null;
  post_call_processed: boolean;
  elevenlabs_conversation_id: string | null;
}

interface TranscriptTurn {
  role: string;
  message: string;
  time_in_call_secs?: number;
}

interface CallDetail extends CallRecord {
  client_id: string;
  recording_url: string | null;
  transcript: {
    turns: TranscriptTurn[];
    summary: string | null;
    sentiment: string | null;
  };
}

const CHANNEL_FILTERS = ["all", "voice", "text"] as const;

export function CallsPage() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CallDetail | null>(null);
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCalls = useCallback(async () => {
    try {
      setLoading(true);
      // The backend accepts channel as a query param
      const res = await getCalls(undefined, 100, 0);
      let items: CallRecord[] = res.calls || [];
      if (channelFilter !== "all") {
        items = items.filter((c) => c.channel === channelFilter);
      }
      setCalls(items);
      setTotal(res.total || 0);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [channelFilter]);

  useEffect(() => {
    loadCalls();
  }, [loadCalls]);

  // Load detail
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    (async () => {
      try {
        setDetailLoading(true);
        const res = await getCall(selectedId);
        setDetail(res);
      } catch {
        setDetail(null);
      } finally {
        setDetailLoading(false);
      }
    })();
  }, [selectedId]);

  async function handleSync() {
    try {
      setSyncing(true);
      const res = await syncCalls();
      // Refresh after sync
      await loadCalls();
    } catch {
      // ignore
    } finally {
      setSyncing(false);
    }
  }

  const channelIcon = (ch: string) => {
    if (ch === "voice") return <Phone className="w-3 h-3" />;
    return <MessageSquare className="w-3 h-3" />;
  };

  const directionIcon = (dir: string) => {
    if (dir === "outbound") return <PhoneOutgoing className="w-3 h-3" />;
    return <PhoneIncoming className="w-3 h-3" />;
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "success";
      case "in-progress":
        return "secondary";
      case "failed":
      case "no-answer":
        return "destructive";
      default:
        return "secondary";
    }
  };

  return (
    <div className="flex h-full">
      {/* Left panel — call list */}
      <div className="w-full lg:w-3/5 border-r border-border flex flex-col">
        {/* Toolbar */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {CHANNEL_FILTERS.map((f) => (
                <Button
                  key={f}
                  size="sm"
                  variant={channelFilter === f ? "default" : "ghost"}
                  className="h-7 text-xs capitalize"
                  onClick={() => {
                    setChannelFilter(f);
                    setSelectedId(null);
                  }}
                >
                  {f}
                </Button>
              ))}
            </div>

            <span className="ml-auto text-xs text-muted-foreground">
              {calls.length} of {total} calls
            </span>

            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs gap-1"
              disabled={syncing}
              onClick={handleSync}
            >
              <RefreshCw
                className={cn("w-3 h-3", syncing && "animate-spin")}
              />
              Sync
            </Button>
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
          ) : calls.length === 0 ? (
            <div className="flex flex-col items-center py-12 gap-2">
              <Phone className="w-8 h-8 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">No calls yet</p>
              <p className="text-xs text-muted-foreground">
                Calls will appear here when your AI agent handles conversations
              </p>
            </div>
          ) : (
            calls.map((call) => (
              <div
                key={call.id}
                onClick={() => setSelectedId(call.id)}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 cursor-pointer border-b border-border hover:bg-accent/50 transition-colors",
                  selectedId === call.id && "bg-accent"
                )}
              >
                {/* Direction icon */}
                <div
                  className={cn(
                    "flex items-center justify-center w-8 h-8 rounded-full shrink-0",
                    call.direction === "outbound"
                      ? "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300"
                      : "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300"
                  )}
                >
                  {directionIcon(call.direction)}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-foreground truncate">
                      {call.caller_number
                        ? formatPhone(call.caller_number)
                        : "Widget call"}
                    </p>
                    <span className="text-muted-foreground">
                      {channelIcon(call.channel)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="capitalize">{call.direction}</span>
                    <span>·</span>
                    <span>{formatDuration(call.duration_seconds)}</span>
                    {call.post_call_processed && (
                      <>
                        <span>·</span>
                        <CheckCircle2 className="w-3 h-3 text-green-500" />
                      </>
                    )}
                  </div>
                </div>

                {/* Right side */}
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <Badge
                    variant={statusColor(call.status) as any}
                    className="text-[10px]"
                  >
                    {call.status}
                  </Badge>
                  <span className="text-[9px] text-muted-foreground">
                    {timeAgo(call.started_at)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right panel — call detail */}
      <div className="hidden lg:flex lg:w-2/5 flex-col overflow-y-auto">
        {detailLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : !detail ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground">
              Select a call to view details
            </p>
          </div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Header */}
            <div>
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    "flex items-center justify-center w-10 h-10 rounded-full shrink-0",
                    detail.direction === "outbound"
                      ? "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300"
                      : "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300"
                  )}
                >
                  {directionIcon(detail.direction)}
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    {detail.caller_number
                      ? formatPhone(detail.caller_number)
                      : "Widget Conversation"}
                  </h2>
                  <p className="text-xs text-muted-foreground capitalize">
                    {detail.direction} · {detail.channel}
                  </p>
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3">
              <Card>
                <CardContent className="p-3 text-center">
                  <p className="text-[10px] text-muted-foreground">Duration</p>
                  <p className="text-sm font-semibold">
                    {formatDuration(detail.duration_seconds)}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <p className="text-[10px] text-muted-foreground">Status</p>
                  <p className="text-sm font-semibold capitalize">
                    {detail.status}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <p className="text-[10px] text-muted-foreground">Sentiment</p>
                  <p className="text-sm font-semibold capitalize">
                    {detail.transcript?.sentiment || "—"}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* AI Summary */}
            {detail.transcript?.summary && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  AI Summary
                </p>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-sm text-foreground leading-relaxed">
                      {detail.transcript.summary}
                    </p>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Transcript */}
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Transcript{" "}
                {detail.transcript?.turns?.length
                  ? `(${detail.transcript.turns.length} turns)`
                  : ""}
              </p>
              {detail.transcript?.turns?.length > 0 ? (
                <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
                  {detail.transcript.turns.map((turn, i) => (
                    <div
                      key={i}
                      className={cn(
                        "flex gap-2",
                        turn.role === "agent" ? "justify-start" : "justify-end"
                      )}
                    >
                      <div
                        className={cn(
                          "px-3 py-2 rounded-lg text-sm max-w-[85%]",
                          turn.role === "agent"
                            ? "bg-primary/10 text-foreground"
                            : "bg-accent text-foreground"
                        )}
                      >
                        <p className="text-[9px] font-medium text-muted-foreground mb-0.5 capitalize">
                          {turn.role}
                          {turn.time_in_call_secs != null && (
                            <span className="ml-1">
                              · {formatDuration(Math.round(turn.time_in_call_secs))}
                            </span>
                          )}
                        </p>
                        <p>{turn.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  No transcript available for this call
                </p>
              )}
            </div>

            {/* Timestamps */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {detail.started_at && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(detail.started_at).toLocaleString()}
                </span>
              )}
              {detail.post_call_processed && (
                <Badge variant="success" className="text-[10px]">
                  Processed
                </Badge>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

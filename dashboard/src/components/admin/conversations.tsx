"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { adminGetConversations } from "@/lib/api";
import { cn, formatDuration, formatPhone, timeAgo } from "@/lib/utils";
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  MessageSquare,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Building2,
} from "lucide-react";

interface Conversation {
  id: string;
  client_id: string;
  client_name: string;
  business_name: string | null;
  caller_number: string;
  direction: string;
  channel: string;
  status: string;
  duration_seconds: number | null;
  started_at: string | null;
  ended_at: string | null;
  post_call_processed: boolean;
  retell_call_id: string | null;
}

const CHANNEL_OPTS = ["all", "voice", "text"] as const;
const STATUS_OPTS = ["all", "completed", "in_progress", "failed", "no_answer"] as const;
const PAGE_SIZE = 30;

export function AdminConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [channel, setChannel] = useState("all");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await adminGetConversations({
        channel: channel === "all" ? undefined : channel,
        status: status === "all" ? undefined : status,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setConversations(res.conversations || []);
      setTotal(res.total || 0);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [channel, status, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Sessions</h1>
          <p className="text-sm text-muted-foreground mt-1">
            All conversations across all client agents
          </p>
        </div>
        <span className="text-sm text-muted-foreground">{total} total</span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1">
          {CHANNEL_OPTS.map((c) => (
            <Button
              key={c}
              size="sm"
              variant={channel === c ? "default" : "ghost"}
              className="h-7 text-xs capitalize"
              onClick={() => { setChannel(c); setPage(0); }}
            >
              {c}
            </Button>
          ))}
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex gap-1">
          {STATUS_OPTS.map((s) => (
            <Button
              key={s}
              size="sm"
              variant={status === s ? "default" : "ghost"}
              className="h-7 text-xs capitalize"
              onClick={() => { setStatus(s); setPage(0); }}
            >
              {s.replace("_", " ")}
            </Button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : conversations.length === 0 ? (
        <div className="text-center py-20">
          <Phone className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No conversations found</p>
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Caller
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Client
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Channel
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Direction
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Status
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Duration
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      When
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {conversations.map((conv) => (
                    <tr key={conv.id} className="hover:bg-accent/30 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className={cn(
                            "w-7 h-7 rounded-full flex items-center justify-center shrink-0",
                            conv.direction === "outbound"
                              ? "bg-blue-500/10 text-blue-400"
                              : "bg-green-500/10 text-green-400"
                          )}>
                            {conv.direction === "outbound" ? (
                              <PhoneOutgoing className="w-3 h-3" />
                            ) : (
                              <PhoneIncoming className="w-3 h-3" />
                            )}
                          </div>
                          <span className="text-foreground font-medium text-xs">
                            {conv.caller_number ? formatPhone(conv.caller_number) : "Widget"}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-xs text-foreground font-medium">
                            {conv.business_name || conv.client_name}
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          {conv.channel === "voice" ? (
                            <Phone className="w-3 h-3" />
                          ) : (
                            <MessageSquare className="w-3 h-3" />
                          )}
                          {conv.channel}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-muted-foreground capitalize">
                          {conv.direction}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant={
                            conv.status === "completed" ? "success"
                            : conv.status === "failed" || conv.status === "no_answer" ? "destructive"
                            : "secondary"
                          }
                          className="text-[9px]"
                        >
                          {conv.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {formatDuration(conv.duration_seconds)}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {timeAgo(conv.started_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button
            size="sm"
            variant="outline"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {page + 1} of {totalPages}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

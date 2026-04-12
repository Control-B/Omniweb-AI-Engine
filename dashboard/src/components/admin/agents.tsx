"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { adminGetAgents } from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";
import {
  Bot,
  Loader2,
  AlertCircle,
  Phone,
  UserCheck,
  Globe,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Zap,
} from "lucide-react";

const LANGUAGE_FLAGS: Record<string, string> = {
  ar: "🇸🇦", de: "🇩🇪", en: "🇺🇸", es: "🇪🇸", fr: "🇫🇷", hi: "🇮🇳",
  it: "🇮🇹", ja: "🇯🇵", ko: "🇰🇷", nl: "🇳🇱", pl: "🇵🇱", pt: "🇧🇷",
  ru: "🇷🇺", tr: "🇹🇷", uk: "🇺🇦", zh: "🇨🇳",
};

const LANGUAGE_LABELS: Record<string, string> = {
  ar: "Arabic", de: "German", en: "English", es: "Spanish", fr: "French", hi: "Hindi",
  it: "Italian", ja: "Japanese", ko: "Korean", nl: "Dutch", pl: "Polish", pt: "Portuguese",
  ru: "Russian", tr: "Turkish", uk: "Ukrainian", zh: "Chinese",
};

const planColors: Record<string, "default" | "success" | "warning" | "secondary"> = {
  starter: "secondary",
  growth: "default",
  pro: "success",
  agency: "warning",
};

interface Agent {
  id: string;
  client_id: string;
  client_name: string;
  client_email: string;
  business_name: string | null;
  plan: string;
  is_active: boolean;
  agent_name: string;
  elevenlabs_agent_id: string | null;
  language: string;
  supported_languages: string[];
  greeting: string;
  system_prompt: string;
  call_count: number;
  lead_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export function AdminAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    adminGetAgents()
      .then((res) => setAgents(res.agents || []))
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

  return (
    <div className="p-6 space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Agents</h1>
          <p className="text-sm text-muted-foreground mt-1">
            All AI agents deployed across client accounts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-foreground">{agents.length}</span>
          <span className="text-sm text-muted-foreground">deployed</span>
        </div>
      </div>

      {/* Agent cards */}
      {agents.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Bot className="w-8 h-8 text-muted-foreground/40 mx-auto mb-3" />
            <p className="text-sm text-foreground font-medium">No agents deployed yet</p>
            <p className="text-xs text-muted-foreground mt-1">
              Agents will appear here when clients are configured
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {agents.map((agent) => {
            const isExpanded = expandedId === agent.id;
            return (
              <Card key={agent.id} className="overflow-hidden">
                {/* Main row */}
                <div
                  className="flex items-center gap-4 p-5 cursor-pointer hover:bg-accent/30 transition-colors"
                  onClick={() => setExpandedId(isExpanded ? null : agent.id)}
                >
                  {/* Agent icon */}
                  <div className={cn(
                    "flex items-center justify-center w-11 h-11 rounded-xl shrink-0",
                    agent.is_active ? "bg-primary/10 text-primary" : "bg-red-500/10 text-red-400"
                  )}>
                    <Bot className="w-5 h-5" />
                  </div>

                  {/* Agent info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-foreground">
                        {agent.agent_name}
                      </p>
                      <Badge variant={agent.is_active ? "success" : "destructive"} className="text-[9px]">
                        {agent.is_active ? "live" : "inactive"}
                      </Badge>
                      <Badge variant={planColors[agent.plan] || "secondary"} className="text-[9px]">
                        {agent.plan}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                      {agent.business_name || agent.client_name} · {agent.client_email}
                    </p>
                  </div>

                  {/* Stats */}
                  <div className="hidden sm:flex items-center gap-5">
                    <div className="text-center">
                      <p className="text-sm font-bold text-foreground">{agent.call_count}</p>
                      <p className="text-[9px] text-muted-foreground">Calls</p>
                    </div>
                    <div className="text-center">
                      <p className="text-sm font-bold text-foreground">{agent.lead_count}</p>
                      <p className="text-[9px] text-muted-foreground">Leads</p>
                    </div>
                    <div className="text-center">
                      <p className="text-sm text-foreground">
                        {LANGUAGE_FLAGS[agent.language] ?? "🌐"}
                      </p>
                      <p className="text-[9px] text-muted-foreground">
                        {LANGUAGE_LABELS[agent.language] ?? agent.language}
                      </p>
                    </div>
                  </div>

                  {/* Expand icon */}
                  <div className="text-muted-foreground shrink-0">
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t border-border p-5 bg-accent/10 space-y-4">
                    {/* Info grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                      <div className="p-3 rounded-lg bg-card border border-border">
                        <p className="text-[10px] text-muted-foreground font-medium">ElevenLabs ID</p>
                        <p className="text-xs text-foreground mt-0.5 font-mono truncate">
                          {agent.elevenlabs_agent_id || "not linked"}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-card border border-border">
                        <p className="text-[10px] text-muted-foreground font-medium">Client ID</p>
                        <p className="text-xs text-foreground mt-0.5 font-mono truncate">
                          {agent.client_id}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-card border border-border">
                        <p className="text-[10px] text-muted-foreground font-medium">Created</p>
                        <p className="text-xs text-foreground mt-0.5">
                          {agent.created_at ? new Date(agent.created_at).toLocaleDateString() : "—"}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-card border border-border">
                        <p className="text-[10px] text-muted-foreground font-medium">Last Updated</p>
                        <p className="text-xs text-foreground mt-0.5">
                          {agent.updated_at ? timeAgo(agent.updated_at) : "—"}
                        </p>
                      </div>
                    </div>

                    {/* Greeting */}
                    <div>
                      <p className="text-[10px] text-muted-foreground font-medium mb-1">Welcome Message</p>
                      <div className="p-3 rounded-lg bg-card border border-border">
                        <p className="text-sm text-foreground">{agent.greeting || "—"}</p>
                      </div>
                    </div>

                    {/* System prompt preview */}
                    {agent.system_prompt && (
                      <div>
                        <p className="text-[10px] text-muted-foreground font-medium mb-1">
                          Instructions Preview
                        </p>
                        <div className="p-3 rounded-lg bg-card border border-border">
                          <p className="text-xs text-muted-foreground font-mono whitespace-pre-wrap">
                            {agent.system_prompt}
                            {agent.system_prompt.length >= 200 && "…"}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Supported languages */}
                    {agent.supported_languages.length > 0 && (
                      <div>
                        <p className="text-[10px] text-muted-foreground font-medium mb-1">
                          Supported Languages ({agent.supported_languages.length})
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {agent.supported_languages.map((code) => (
                            <Badge key={code} variant="outline" className="text-[11px] px-2 py-0.5 gap-1">
                              <span>{LANGUAGE_FLAGS[code] ?? "🌐"}</span>
                              {LANGUAGE_LABELS[code] ?? code}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

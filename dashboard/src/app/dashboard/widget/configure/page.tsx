"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { getMeWorkspace, patchWidgetConfig } from "@/lib/api";

const TONES = ["Professional", "Friendly", "Luxury", "Direct", "Helpful"] as const;

export default function WidgetConfigurePage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [agentName, setAgentName] = useState("");
  const [welcome, setWelcome] = useState("");
  const [instructions, setInstructions] = useState("");
  const [tone, setTone] = useState("Professional");
  const [leadQs, setLeadQs] = useState("");
  const [cta, setCta] = useState("");
  const [color, setColor] = useState("#6366f1");
  const [position, setPosition] = useState<"bottom-right" | "bottom-left">("bottom-right");
  const [knowledgeUrl, setKnowledgeUrl] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ws = await getMeWorkspace();
        if (cancelled) return;
        setAgentName(ws.widget.agent_name || "");
        setWelcome(ws.widget.welcome_message || "");
        setInstructions(ws.widget_config.business_instructions || "");
        setTone(
          TONES.find((t) => t.toLowerCase() === (ws.widget_config.tone || "").toLowerCase()) || "Professional"
        );
        setLeadQs((ws.widget_config.lead_questions || []).join("\n"));
        setCta(ws.widget_config.call_to_action || "");
        setColor(ws.widget.theme_color || "#6366f1");
        setPosition((ws.widget.position as "bottom-right" | "bottom-left") || "bottom-right");
        setKnowledgeUrl(ws.widget_config.knowledge_source_url || "");
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Load failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      await patchWidgetConfig({
        agent_name: agentName,
        welcome_message: welcome,
        business_instructions: instructions,
        tone: tone.toLowerCase(),
        lead_questions: leadQs
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        call_to_action: cta,
        theme_color: color,
        position,
        knowledge_source_url: knowledgeUrl,
        widget_status: "active",
      });
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Configure AI agent</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Fine-tune how your widget sounds and behaves. Defaults are pre-filled from onboarding.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Widget &amp; agent</CardTitle>
          <CardDescription>Changes apply to your site widget and preview.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSave} className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Agent name</Label>
                <Input value={agentName} onChange={(e) => setAgentName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Tone</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                >
                  {TONES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Welcome message</Label>
              <Textarea value={welcome} onChange={(e) => setWelcome(e.target.value)} rows={2} />
            </div>
            <div className="space-y-1.5">
              <Label>Business instructions</Label>
              <Textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={6} />
            </div>
            <div className="space-y-1.5">
              <Label>Lead questions (one per line)</Label>
              <Textarea value={leadQs} onChange={(e) => setLeadQs(e.target.value)} rows={3} className="font-mono text-xs" />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Call to action</Label>
                <Input value={cta} onChange={(e) => setCta(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Knowledge source URL</Label>
                <Input value={knowledgeUrl} onChange={(e) => setKnowledgeUrl(e.target.value)} placeholder="https://…" />
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Theme color</Label>
                <Input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="h-10" />
              </div>
              <div className="space-y-1.5">
                <Label>Position</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={position}
                  onChange={(e) => setPosition(e.target.value as "bottom-right" | "bottom-left")}
                >
                  <option value="bottom-right">Bottom right</option>
                  <option value="bottom-left">Bottom left</option>
                </select>
              </div>
            </div>
            {err && <p className="text-sm text-destructive">{err}</p>}
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save
              </Button>
              <Button type="button" variant="outline" asChild>
                <Link href="/dashboard/widget/test">Test widget</Link>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

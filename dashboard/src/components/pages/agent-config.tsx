"use client";

import { useState } from "react";
import { Save, RotateCcw, Volume2, Brain, Clock, Wrench, MessageSquare } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { MOCK_AGENT_CONFIG, type AgentConfigData } from "@/lib/mock-data";

const VOICE_OPTIONS = [
  { id: "21m00Tcm4TlvDq8ikWAM", name: "Rachel", accent: "American", style: "Warm & Professional" },
  { id: "EXAVITQu4vr4xnSDxMaL", name: "Bella", accent: "American", style: "Soft & Engaging" },
  { id: "yoZ06aMxZJJ28mfd3POQ", name: "Sam", accent: "American", style: "Male, Authoritative" },
  { id: "pNInz6obpgDQGcFmaJgB", name: "Adam", accent: "American", style: "Male, Deep" },
];

const LLM_OPTIONS = [
  { id: "gpt-4o", label: "GPT-4o", desc: "Best quality, smartest" },
  { id: "gpt-4o-mini", label: "GPT-4o Mini", desc: "Faster, cheaper" },
  { id: "gpt-4.1-mini", label: "GPT-4.1 Mini", desc: "Newest, balanced" },
];

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

export function AgentConfigPage() {
  const [config, setConfig] = useState<AgentConfigData>(MOCK_AGENT_CONFIG);
  const [activeTab, setActiveTab] = useState<"personality" | "voice" | "brain" | "hours" | "sms">("personality");
  const [saved, setSaved] = useState(false);

  const update = (field: keyof AgentConfigData, value: any) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const tabs = [
    { id: "personality", label: "Personality", icon: MessageSquare },
    { id: "voice", label: "Voice & Sound", icon: Volume2 },
    { id: "brain", label: "AI Brain", icon: Brain },
    { id: "hours", label: "Business Hours", icon: Clock },
    { id: "sms", label: "Services & SMS", icon: Wrench },
  ] as const;

  return (
    <div className="p-6 space-y-4 max-w-[900px]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">AI Agent Configuration</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Customize how your AI phone agent behaves, sounds, and responds
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setConfig(MOCK_AGENT_CONFIG)}>
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </Button>
          <Button size="sm" onClick={handleSave}>
            <Save className="w-3.5 h-3.5" />
            {saved ? "Saved ✓" : "Save Changes"}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg bg-secondary">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium transition-colors flex-1 justify-center",
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "personality" && (
        <Card>
          <CardHeader>
            <CardTitle>Agent Personality</CardTitle>
            <CardDescription>Define who your AI agent is and how it greets callers</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Agent Name</Label>
                <Input
                  value={config.agent_name}
                  onChange={(e) => update("agent_name", e.target.value)}
                  placeholder="e.g. Aria, Max, Sarah"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Business Name</Label>
                <Input
                  value={config.business_name}
                  onChange={(e) => update("business_name", e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Greeting Message</Label>
              <Textarea
                value={config.agent_greeting}
                onChange={(e) => update("agent_greeting", e.target.value)}
                rows={2}
                placeholder="The first thing your agent says when answering a call"
              />
              <p className="text-[11px] text-muted-foreground">
                Tip: Keep it short and warm. The caller should feel welcome within 3 seconds.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label>System Prompt (Agent Instructions)</Label>
              <Textarea
                value={config.system_prompt}
                onChange={(e) => update("system_prompt", e.target.value)}
                rows={12}
                className="font-mono text-xs"
              />
              <p className="text-[11px] text-muted-foreground">
                This is the &quot;brain&quot; of your agent. Tell it your services, goals, and how to handle different scenarios.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label>Business Type</Label>
              <Input
                value={config.business_type}
                onChange={(e) => update("business_type", e.target.value)}
                placeholder="plumbing, dental, law firm, etc."
              />
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "voice" && (
        <Card>
          <CardHeader>
            <CardTitle>Voice & Sound</CardTitle>
            <CardDescription>Choose how your agent sounds on the phone</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label>Voice</Label>
              <div className="grid grid-cols-2 gap-2">
                {VOICE_OPTIONS.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => update("voice_id", v.id)}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border transition-colors text-left",
                      config.voice_id === v.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/30"
                    )}
                  >
                    <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                      <Volume2 className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{v.name}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {v.accent} · {v.style}
                      </p>
                    </div>
                    {config.voice_id === v.id && (
                      <Badge variant="default" className="ml-auto text-[9px]">selected</Badge>
                    )}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Voice Stability: {config.voice_stability.toFixed(2)}</Label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={config.voice_stability}
                  onChange={(e) => update("voice_stability", parseFloat(e.target.value))}
                  className="w-full accent-primary"
                />
                <p className="text-[11px] text-muted-foreground">
                  Lower = more expressive, Higher = more consistent
                </p>
              </div>
              <div className="space-y-2">
                <Label>Similarity Boost: {config.voice_similarity_boost.toFixed(2)}</Label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={config.voice_similarity_boost}
                  onChange={(e) => update("voice_similarity_boost", parseFloat(e.target.value))}
                  className="w-full accent-primary"
                />
                <p className="text-[11px] text-muted-foreground">
                  Higher = closer to original voice
                </p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-accent/50 flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-muted-foreground shrink-0" />
              <p className="text-xs text-muted-foreground">
                Voice preview will play a sample of your agent&apos;s greeting when connected to ElevenLabs.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "brain" && (
        <Card>
          <CardHeader>
            <CardTitle>AI Brain Settings</CardTitle>
            <CardDescription>Control the intelligence and responsiveness of your agent</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label>LLM Model</Label>
              <div className="grid grid-cols-3 gap-2">
                {LLM_OPTIONS.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => update("llm_model", m.id)}
                    className={cn(
                      "p-3 rounded-lg border transition-colors text-left",
                      config.llm_model === m.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/30"
                    )}
                  >
                    <p className="text-sm font-medium text-foreground">{m.label}</p>
                    <p className="text-[11px] text-muted-foreground">{m.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Temperature: {config.temperature.toFixed(1)}</Label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={config.temperature}
                onChange={(e) => update("temperature", parseFloat(e.target.value))}
                className="w-full accent-primary"
              />
              <p className="text-[11px] text-muted-foreground">
                Lower = more focused & predictable · Higher = more creative & varied
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  Allow Interruptions
                  <input
                    type="checkbox"
                    checked={config.allow_interruptions}
                    onChange={(e) => update("allow_interruptions", e.target.checked)}
                    className="accent-primary"
                  />
                </Label>
                <p className="text-[11px] text-muted-foreground">
                  Let callers interrupt the agent mid-sentence (more natural)
                </p>
              </div>
              <div className="space-y-2">
                <Label>Endpointing Delay: {config.min_endpointing_delay}s – {config.max_endpointing_delay}s</Label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="2"
                    value={config.min_endpointing_delay}
                    onChange={(e) => update("min_endpointing_delay", parseFloat(e.target.value))}
                    className="w-20"
                  />
                  <span className="text-muted-foreground self-center">to</span>
                  <Input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="3"
                    value={config.max_endpointing_delay}
                    onChange={(e) => update("max_endpointing_delay", parseFloat(e.target.value))}
                    className="w-20"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Seconds of silence before the agent considers the caller done speaking
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "hours" && (
        <Card>
          <CardHeader>
            <CardTitle>Business Hours</CardTitle>
            <CardDescription>Set when your business is open — the agent adjusts behavior accordingly</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              {DAYS.map((day) => {
                const hours = config.business_hours[day];
                const isOpen = hours !== null && hours !== undefined;
                return (
                  <div key={day} className="flex items-center gap-3 py-2">
                    <div className="w-24">
                      <span className="text-sm font-medium capitalize text-foreground">{day}</span>
                    </div>
                    <input
                      type="checkbox"
                      checked={isOpen}
                      onChange={(e) => {
                        const newHours = { ...config.business_hours };
                        newHours[day] = e.target.checked ? { open: "09:00", close: "17:00" } : null;
                        update("business_hours", newHours);
                      }}
                      className="accent-primary"
                    />
                    {isOpen ? (
                      <div className="flex items-center gap-2">
                        <Input
                          type="time"
                          value={hours.open}
                          onChange={(e) => {
                            const newHours = { ...config.business_hours };
                            newHours[day] = { ...hours, open: e.target.value };
                            update("business_hours", newHours);
                          }}
                          className="w-28"
                        />
                        <span className="text-xs text-muted-foreground">to</span>
                        <Input
                          type="time"
                          value={hours.close}
                          onChange={(e) => {
                            const newHours = { ...config.business_hours };
                            newHours[day] = { ...hours, close: e.target.value };
                            update("business_hours", newHours);
                          }}
                          className="w-28"
                        />
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">Closed</span>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="border-t border-border pt-4 space-y-3">
              <div className="space-y-1.5">
                <Label>After-Hours Message</Label>
                <Textarea
                  value={config.after_hours_message}
                  onChange={(e) => update("after_hours_message", e.target.value)}
                  rows={2}
                />
              </div>
              <Label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={config.after_hours_sms_enabled}
                  onChange={(e) => update("after_hours_sms_enabled", e.target.checked)}
                  className="accent-primary"
                />
                Send SMS follow-up for after-hours calls
              </Label>
            </div>

            <div className="space-y-1.5">
              <Label>Timezone</Label>
              <Input
                value={config.timezone}
                onChange={(e) => update("timezone", e.target.value)}
                placeholder="America/New_York"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "sms" && (
        <Card>
          <CardHeader>
            <CardTitle>Services & Follow-Up</CardTitle>
            <CardDescription>List your services and configure booking & SMS settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Services Offered</Label>
              <div className="flex flex-wrap gap-1.5">
                {config.services.map((s, i) => (
                  <Badge key={i} variant="outline" className="gap-1">
                    {s}
                    <button
                      onClick={() => update("services", config.services.filter((_, idx) => idx !== i))}
                      className="text-muted-foreground hover:text-foreground ml-0.5"
                    >
                      ×
                    </button>
                  </Badge>
                ))}
              </div>
              <Input
                placeholder="Add a service and press Enter"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                    update("services", [...config.services, (e.target as HTMLInputElement).value.trim()]);
                    (e.target as HTMLInputElement).value = "";
                  }
                }}
              />
            </div>

            <div className="space-y-1.5">
              <Label>Online Booking URL</Label>
              <Input
                value={config.booking_url}
                onChange={(e) => update("booking_url", e.target.value)}
                placeholder="https://calendly.com/your-business"
              />
              <p className="text-[11px] text-muted-foreground">
                The agent will direct callers here for self-service booking
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

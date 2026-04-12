"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Save,
  Volume2,
  Brain,
  MessageSquare,
  Code,
  ExternalLink,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  Zap,
  Bot,
  Globe,
  BookOpen,
  Upload,
  FileText,
  Link2,
  Trash2,
  Plus,
  X,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import {
  getAgentConfig,
  updateAgentConfig,
  getWidgetEmbed,
  getKnowledgeBase,
  createKbFromText,
  createKbFromUrl,
  uploadKbFile,
  deleteKbDocument,
} from "@/lib/api";

const VOICE_OPTIONS = [
  { id: "EXAVITQu4vr4xnSDxMaL", name: "Rachel", accent: "American", style: "Warm & Professional" },
  { id: "21m00Tcm4TlvDq8ikWAM", name: "Adam", accent: "American", style: "Deep & Authoritative" },
  { id: "yoZ06aMxZJJ28mfd3POQ", name: "Sam", accent: "American", style: "Casual & Friendly" },
  { id: "pNInz6obpgDQGcFmaJgB", name: "Josh", accent: "American", style: "Conversational" },
];

const LANGUAGE_OPTIONS = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "es", label: "Spanish", flag: "🇪🇸" },
  { code: "fr", label: "French", flag: "🇫🇷" },
  { code: "de", label: "German", flag: "🇩🇪" },
  { code: "ar", label: "Arabic", flag: "🇸🇦" },
  { code: "hi", label: "Hindi", flag: "🇮🇳" },
  { code: "pt", label: "Portuguese", flag: "🇧🇷" },
  { code: "it", label: "Italian", flag: "🇮🇹" },
  { code: "ja", label: "Japanese", flag: "🇯🇵" },
  { code: "ko", label: "Korean", flag: "🇰🇷" },
  { code: "zh", label: "Chinese", flag: "🇨🇳" },
  { code: "nl", label: "Dutch", flag: "🇳🇱" },
  { code: "pl", label: "Polish", flag: "🇵🇱" },
  { code: "ru", label: "Russian", flag: "🇷🇺" },
  { code: "tr", label: "Turkish", flag: "🇹🇷" },
  { code: "uk", label: "Ukrainian", flag: "🇺🇦" },
];

interface AgentConfig {
  id: string;
  client_id: string;
  agent_name: string;
  agent_greeting: string;
  system_prompt: string;
  voice_id: string;
  voice_stability: number;
  voice_similarity_boost: number;
  llm_model: string;
  temperature: number;
  business_name: string;
  business_type: string;
  elevenlabs_agent_id: string | null;
  supported_languages: string[];
  [key: string]: any;
}

interface WidgetInfo {
  agent_id: string;
  embed_code: string;
  talk_url: string;
}

export function AgentConfigPage() {
  const { user } = useAuth();
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [widget, setWidget] = useState<WidgetInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"personality" | "voice" | "brain" | "languages" | "knowledge" | "widget">("personality");

  // Knowledge Base state
  const [kbDocs, setKbDocs] = useState<any[]>([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [kbUploading, setKbUploading] = useState(false);
  const [kbError, setKbError] = useState("");
  const [kbAddMode, setKbAddMode] = useState<"" | "text" | "url" | "file">("");
  const [kbTextName, setKbTextName] = useState("");
  const [kbTextContent, setKbTextContent] = useState("");
  const [kbUrlName, setKbUrlName] = useState("");
  const [kbUrlValue, setKbUrlValue] = useState("");
  const [kbFileName, setKbFileName] = useState("");
  const [kbFile, setKbFile] = useState<File | null>(null);

  const clientId = user?.client_id || "";

  const loadConfig = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    setError("");
    try {
      const data = await getAgentConfig(clientId);
      setConfig(data);
      try {
        const w = await getWidgetEmbed(clientId);
        setWidget(w);
      } catch {
        setWidget(null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load agent config");
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  const loadKbDocs = useCallback(async () => {
    setKbLoading(true);
    setKbError("");
    try {
      const data = await getKnowledgeBase();
      setKbDocs(data.documents || []);
    } catch (err: any) {
      setKbError(err.message || "Failed to load knowledge base");
    } finally {
      setKbLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  useEffect(() => {
    if (activeTab === "knowledge") loadKbDocs();
  }, [activeTab, loadKbDocs]);

  const update = (field: string, value: any) => {
    if (!config) return;
    setConfig({ ...config, [field]: value });
    setSaved(false);
  };

  const handleSave = async () => {
    if (!config || !clientId) return;
    setSaving(true);
    setError("");
    try {
      await updateAgentConfig(clientId, {
        agent_name: config.agent_name,
        agent_greeting: config.agent_greeting,
        system_prompt: config.system_prompt,
        voice_id: config.voice_id,
        voice_stability: config.voice_stability,
        voice_similarity_boost: config.voice_similarity_boost,
        llm_model: config.llm_model,
        temperature: config.temperature,
        business_name: config.business_name,
        business_type: config.business_type,
        supported_languages: config.supported_languages,
      });
      setSaved(true);
      await loadConfig();
      setTimeout(() => setSaved(false), 2000);
    } catch (err: any) {
      setError(err.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const resetKbForm = () => {
    setKbAddMode("");
    setKbTextName("");
    setKbTextContent("");
    setKbUrlName("");
    setKbUrlValue("");
    setKbFileName("");
    setKbFile(null);
  };

  const handleKbAddText = async () => {
    if (!kbTextContent.trim()) return;
    setKbUploading(true);
    setKbError("");
    try {
      await createKbFromText(kbTextContent, kbTextName || undefined);
      resetKbForm();
      await loadKbDocs();
    } catch (err: any) {
      setKbError(err.message || "Failed to add text");
    } finally {
      setKbUploading(false);
    }
  };

  const handleKbAddUrl = async () => {
    if (!kbUrlValue.trim()) return;
    setKbUploading(true);
    setKbError("");
    try {
      await createKbFromUrl(kbUrlValue, kbUrlName || undefined);
      resetKbForm();
      await loadKbDocs();
    } catch (err: any) {
      setKbError(err.message || "Failed to add URL");
    } finally {
      setKbUploading(false);
    }
  };

  const handleKbUploadFile = async () => {
    if (!kbFile) return;
    setKbUploading(true);
    setKbError("");
    try {
      await uploadKbFile(kbFile, kbFileName || undefined);
      resetKbForm();
      await loadKbDocs();
    } catch (err: any) {
      setKbError(err.message || "Failed to upload file");
    } finally {
      setKbUploading(false);
    }
  };

  const handleKbDelete = async (docId: string) => {
    if (!confirm("Delete this document? The agent will no longer have access to it.")) return;
    try {
      await deleteKbDocument(docId);
      setKbDocs((prev) => prev.filter((d) => d.id !== docId));
    } catch (err: any) {
      setKbError(err.message || "Failed to delete");
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !config) {
    return (
      <div className="p-6">
        <Card className="border-destructive/50">
          <CardContent className="p-6 flex items-center gap-3 text-destructive">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={loadConfig} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!config) return null;

  const tabs = [
    { id: "personality" as const, label: "Personality", icon: MessageSquare },
    { id: "voice" as const, label: "Voice", icon: Volume2 },
    { id: "brain" as const, label: "AI Brain", icon: Brain },
    { id: "languages" as const, label: "Languages", icon: Globe },
    { id: "knowledge" as const, label: "Knowledge Base", icon: BookOpen },
    { id: "widget" as const, label: "Widget & Embed", icon: Code },
  ];

  return (
    <div className="p-6 space-y-4 max-w-[900px]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">AI Agent Configuration</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Customize your AI agent and get your embed code
          </p>
        </div>
        <div className="flex items-center gap-2">
          {config.elevenlabs_agent_id ? (
            <Badge variant="success" className="gap-1">
              <Zap className="w-3 h-3" />
              Agent Live
            </Badge>
          ) : (
            <Badge variant="secondary" className="gap-1">
              <Bot className="w-3 h-3" />
              Not Created
            </Badge>
          )}
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            {saved ? "Saved ✓" : saving ? "Saving..." : "Save & Deploy"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">{error}</div>
      )}

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
                <Input value={config.agent_name || ""} onChange={(e) => update("agent_name", e.target.value)} placeholder="e.g. Aria" />
              </div>
              <div className="space-y-1.5">
                <Label>Business Name</Label>
                <Input value={config.business_name || ""} onChange={(e) => update("business_name", e.target.value)} placeholder="e.g. Bob's Plumbing" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Greeting Message</Label>
              <Textarea value={config.agent_greeting || ""} onChange={(e) => update("agent_greeting", e.target.value)} placeholder="Hello! Thanks for calling. How can I help you today?" rows={3} />
              <p className="text-xs text-muted-foreground">The first thing your agent says when a call or chat begins</p>
            </div>
            <div className="space-y-1.5">
              <Label>System Prompt</Label>
              <Textarea value={config.system_prompt || ""} onChange={(e) => update("system_prompt", e.target.value)} placeholder="You are a friendly AI receptionist for..." rows={8} className="font-mono text-xs" />
              <p className="text-xs text-muted-foreground">Instructions that define your agent&apos;s behavior, personality, and knowledge</p>
            </div>
            <div className="space-y-1.5">
              <Label>Business Type</Label>
              <Input value={config.business_type || ""} onChange={(e) => update("business_type", e.target.value)} placeholder="plumbing, dental, law firm, etc." />
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "voice" && (
        <Card>
          <CardHeader>
            <CardTitle>Voice Settings</CardTitle>
            <CardDescription>Choose how your agent sounds</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>Voice</Label>
              <div className="grid grid-cols-2 gap-2">
                {VOICE_OPTIONS.map((v) => (
                  <button key={v.id} onClick={() => update("voice_id", v.id)} className={cn("p-3 rounded-lg border text-left transition-colors", config.voice_id === v.id ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground/50")}>
                    <div className="font-medium text-sm">{v.name}</div>
                    <div className="text-xs text-muted-foreground">{v.accent} · {v.style}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Stability ({(config.voice_stability ?? 0.5).toFixed(1)})</Label>
                <input type="range" min="0" max="1" step="0.1" value={config.voice_stability ?? 0.5} onChange={(e) => update("voice_stability", parseFloat(e.target.value))} className="w-full accent-primary" />
                <div className="flex justify-between text-xs text-muted-foreground"><span>More variable</span><span>More stable</span></div>
              </div>
              <div className="space-y-1.5">
                <Label>Clarity ({(config.voice_similarity_boost ?? 0.8).toFixed(1)})</Label>
                <input type="range" min="0" max="1" step="0.1" value={config.voice_similarity_boost ?? 0.8} onChange={(e) => update("voice_similarity_boost", parseFloat(e.target.value))} className="w-full accent-primary" />
                <div className="flex justify-between text-xs text-muted-foreground"><span>More natural</span><span>More clear</span></div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "brain" && (
        <Card>
          <CardHeader>
            <CardTitle>AI Brain</CardTitle>
            <CardDescription>Configure the language model powering your agent</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>LLM Model</Label>
              <div className="space-y-2">
                {[
                  { id: "gpt-4o", label: "GPT-4o", desc: "Best quality, smartest" },
                  { id: "gpt-4o-mini", label: "GPT-4o Mini", desc: "Faster, cheaper" },
                  { id: "claude-3.5-sonnet", label: "Claude 3.5 Sonnet", desc: "Great reasoning" },
                ].map((m) => (
                  <button key={m.id} onClick={() => update("llm_model", m.id)} className={cn("w-full p-3 rounded-lg border text-left transition-colors", config.llm_model === m.id ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground/50")}>
                    <div className="font-medium text-sm">{m.label}</div>
                    <div className="text-xs text-muted-foreground">{m.desc}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Temperature ({(config.temperature ?? 0.7).toFixed(1)})</Label>
              <input type="range" min="0" max="1" step="0.1" value={config.temperature ?? 0.7} onChange={(e) => update("temperature", parseFloat(e.target.value))} className="w-full accent-primary" />
              <div className="flex justify-between text-xs text-muted-foreground"><span>Precise & focused</span><span>Creative & varied</span></div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "languages" && (
        <Card>
          <CardHeader>
            <CardTitle>Supported Languages</CardTitle>
            <CardDescription>
              Choose which languages your AI agent can speak. Your agent will automatically greet callers in their selected language.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {(config.supported_languages?.length ?? 1)} of {LANGUAGE_OPTIONS.length} languages enabled
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => update("supported_languages", LANGUAGE_OPTIONS.map(l => l.code))}
                  className="text-xs text-primary hover:underline"
                >
                  Enable all
                </button>
                <span className="text-muted-foreground">·</span>
                <button
                  onClick={() => update("supported_languages", ["en"])}
                  className="text-xs text-muted-foreground hover:underline"
                >
                  English only
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {LANGUAGE_OPTIONS.map((lang) => {
                const enabled = config.supported_languages?.includes(lang.code) ?? lang.code === "en";
                const isEnglish = lang.code === "en";
                return (
                  <button
                    key={lang.code}
                    onClick={() => {
                      if (isEnglish) return; // English is always required
                      const current = config.supported_languages ?? ["en"];
                      const next = enabled
                        ? current.filter((c: string) => c !== lang.code)
                        : [...current, lang.code];
                      update("supported_languages", next);
                    }}
                    className={cn(
                      "flex items-center gap-2 p-3 rounded-lg border text-left transition-colors",
                      enabled
                        ? "border-primary bg-primary/5 text-foreground"
                        : "border-border text-muted-foreground hover:border-muted-foreground/50",
                      isEnglish && "cursor-default"
                    )}
                  >
                    <span className="text-lg">{lang.flag}</span>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{lang.label}</div>
                      <div className="text-[10px] uppercase tracking-wider opacity-60">{lang.code}</div>
                    </div>
                    {isEnglish && (
                      <Badge variant="secondary" className="ml-auto text-[9px] px-1.5">Required</Badge>
                    )}
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              When a caller or visitor selects a language, the AI agent will use that language for speech recognition, responses, and text chat. The widget will show a language selector.
            </p>
          </CardContent>
        </Card>
      )}

      {activeTab === "knowledge" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Knowledge Base</CardTitle>
                  <CardDescription>
                    Upload documents, text, or URLs to give your agent custom knowledge
                  </CardDescription>
                </div>
                {!kbAddMode && (
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => setKbAddMode("text")}>
                      <FileText className="w-3.5 h-3.5" /> Add Text
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setKbAddMode("url")}>
                      <Link2 className="w-3.5 h-3.5" /> Add URL
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setKbAddMode("file")}>
                      <Upload className="w-3.5 h-3.5" /> Upload File
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {kbError && (
                <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {kbError}
                </div>
              )}

              {/* ── Add Text form ── */}
              {kbAddMode === "text" && (
                <Card className="border-primary/30 bg-primary/[0.02]">
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium flex items-center gap-1.5">
                        <FileText className="w-4 h-4" /> Add Text Content
                      </span>
                      <button onClick={resetKbForm} className="text-muted-foreground hover:text-foreground">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Name (optional)</Label>
                      <Input
                        value={kbTextName}
                        onChange={(e) => setKbTextName(e.target.value)}
                        placeholder="e.g. Company FAQ, Pricing info"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Content</Label>
                      <Textarea
                        value={kbTextContent}
                        onChange={(e) => setKbTextContent(e.target.value)}
                        placeholder="Paste your knowledge content here...\n\nExample: Our business hours are Monday-Friday 9am-5pm..."
                        rows={6}
                        className="font-mono text-xs"
                      />
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={resetKbForm}>Cancel</Button>
                      <Button size="sm" onClick={handleKbAddText} disabled={kbUploading || !kbTextContent.trim()}>
                        {kbUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                        {kbUploading ? "Adding..." : "Add to Knowledge Base"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* ── Add URL form ── */}
              {kbAddMode === "url" && (
                <Card className="border-primary/30 bg-primary/[0.02]">
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium flex items-center gap-1.5">
                        <Link2 className="w-4 h-4" /> Add from URL
                      </span>
                      <button onClick={resetKbForm} className="text-muted-foreground hover:text-foreground">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Name (optional)</Label>
                      <Input
                        value={kbUrlName}
                        onChange={(e) => setKbUrlName(e.target.value)}
                        placeholder="e.g. About Us Page"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>URL</Label>
                      <Input
                        value={kbUrlValue}
                        onChange={(e) => setKbUrlValue(e.target.value)}
                        placeholder="https://example.com/about"
                        type="url"
                      />
                      <p className="text-xs text-muted-foreground">The page content will be scraped and added to your agent&apos;s knowledge</p>
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={resetKbForm}>Cancel</Button>
                      <Button size="sm" onClick={handleKbAddUrl} disabled={kbUploading || !kbUrlValue.trim()}>
                        {kbUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                        {kbUploading ? "Adding..." : "Add to Knowledge Base"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* ── Upload File form ── */}
              {kbAddMode === "file" && (
                <Card className="border-primary/30 bg-primary/[0.02]">
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium flex items-center gap-1.5">
                        <Upload className="w-4 h-4" /> Upload File
                      </span>
                      <button onClick={resetKbForm} className="text-muted-foreground hover:text-foreground">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Display Name (optional)</Label>
                      <Input
                        value={kbFileName}
                        onChange={(e) => setKbFileName(e.target.value)}
                        placeholder="e.g. Product Catalog 2026"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>File</Label>
                      <input
                        type="file"
                        accept=".pdf,.txt,.docx,.doc,.md,.csv,.html"
                        onChange={(e) => setKbFile(e.target.files?.[0] || null)}
                        className="block w-full text-sm text-muted-foreground
                          file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border
                          file:border-border file:text-sm file:font-medium
                          file:bg-background file:text-foreground
                          hover:file:bg-secondary cursor-pointer"
                      />
                      <p className="text-xs text-muted-foreground">Supported: PDF, TXT, DOCX, DOC, MD, CSV, HTML — max 25 MB</p>
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={resetKbForm}>Cancel</Button>
                      <Button size="sm" onClick={handleKbUploadFile} disabled={kbUploading || !kbFile}>
                        {kbUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                        {kbUploading ? "Uploading..." : "Upload"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* ── Documents list ── */}
              {kbLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
              ) : kbDocs.length === 0 ? (
                <div className="text-center py-10">
                  <BookOpen className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
                  <h3 className="font-medium mb-1">No documents yet</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Add text, URLs, or upload files to give your agent custom knowledge about your business.
                  </p>
                  {!kbAddMode && (
                    <Button size="sm" variant="outline" onClick={() => setKbAddMode("text")}>
                      <Plus className="w-3.5 h-3.5" /> Add Your First Document
                    </Button>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  {kbDocs.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-secondary/50 transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 rounded-md bg-secondary">
                          <FileText className="w-4 h-4 text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{doc.name || doc.id}</p>
                          <p className="text-xs text-muted-foreground">
                            {doc.type && <span className="capitalize">{doc.type}</span>}
                            {doc.type && doc.size_bytes && " · "}
                            {doc.size_bytes && `${(doc.size_bytes / 1024).toFixed(0)} KB`}
                            {!doc.type && !doc.size_bytes && <span className="font-mono">{doc.id}</span>}
                          </p>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handleKbDelete(doc.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground px-1">
            Documents are automatically attached to your AI agent. The agent will use this knowledge when answering questions from callers and chat visitors.
          </p>
        </div>
      )}

      {activeTab === "widget" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Agent Status</CardTitle>
              <CardDescription>
                {config.elevenlabs_agent_id ? "Your AI agent is live and ready" : "Save your config to create your agent"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {config.elevenlabs_agent_id ? (
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-sm font-medium text-green-500">Active</span>
                  <span className="text-xs text-muted-foreground ml-2 font-mono">{config.elevenlabs_agent_id}</span>
                  {/* Agent ID shown for debugging — brand name hidden */}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-sm">Click &quot;Save &amp; Deploy&quot; to create your agent</span>
                </div>
              )}
            </CardContent>
          </Card>

          {widget && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Embed Code</CardTitle>
                  <CardDescription>Add this snippet to your website to show the chat widget</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="relative">
                    <pre className="bg-secondary p-4 rounded-lg text-xs overflow-x-auto font-mono">{widget.embed_code}</pre>
                    <Button size="sm" variant="outline" className="absolute top-2 right-2" onClick={() => copyToClipboard(widget.embed_code, "embed")}>
                      {copied === "embed" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">Paste this into your website HTML. Supports both voice calls and text chat.</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Test Your Agent</CardTitle>
                  <CardDescription>Try your agent before deploying to your website</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => window.open(widget.talk_url, "_blank")}>
                      <ExternalLink className="w-3.5 h-3.5" />
                      Open Test Page
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(widget.talk_url, "url")}>
                      {copied === "url" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                      Copy Link
                    </Button>
                  </div>
                  <div className="bg-secondary px-3 py-2 rounded-md text-xs text-muted-foreground font-mono break-all">{widget.talk_url}</div>
                </CardContent>
              </Card>
            </>
          )}

          {!widget && !config.elevenlabs_agent_id && (
            <Card>
              <CardContent className="p-8 text-center">
                <Bot className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
                <h3 className="font-medium mb-1">No Agent Yet</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Configure your agent&apos;s personality, voice, and prompt, then click &quot;Save &amp; Deploy&quot; to create it.
                </p>
                <Button size="sm" onClick={() => setActiveTab("personality")}>
                  <MessageSquare className="w-3.5 h-3.5" />
                  Start Configuring
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

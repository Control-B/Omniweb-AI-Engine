"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  ArrowUp,
  Save,
  Volume2,
  Brain,
  MessageSquare,
  MessageCircle,
  Code,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  Search,
  MapPin,
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
  Mic,
  Phone,
  PhoneCall,
  Square,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Label } from "@/components/ui/input";
import { cn, formatPhone } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import {
  DeepgramVoiceAgentSession,
  type TranscriptLine,
} from "@/lib/deepgramVoiceAgentClient";
import {
  getAgentConfig,
  updateAgentConfig,
  getWidgetEmbed,
  getKnowledgeBase,
  createKbFromText,
  createKbFromUrl,
  uploadKbFile,
  deleteKbDocument,
  startRetellPhoneCall,
  getNumbers,
  searchAvailableNumbers,
  buyNumber,
  type WidgetEmbedResponse,
} from "@/lib/api";

const VOICE_OPTIONS = [
  { id: "EXAVITQu4vr4xnSDxMaL", name: "Rachel", accent: "American", style: "Warm & Professional" },
  { id: "21m00Tcm4TlvDq8ikWAM", name: "Adam", accent: "American", style: "Deep & Authoritative" },
  { id: "yoZ06aMxZJJ28mfd3POQ", name: "Sam", accent: "American", style: "Casual & Friendly" },
  { id: "pNInz6obpgDQGcFmaJgB", name: "Josh", accent: "American", style: "Conversational" },
];

const PRIMARY_GOALS = [
  { id: "all", label: "All Goals", desc: "Enable every capability below" },
  { id: "product_recommendations", label: "Product Recommendations", desc: "Help shoppers find the right products" },
  { id: "customer_support", label: "Customer Support & FAQs", desc: "Answer common questions and policies" },
  { id: "cart_management", label: "Cart Management & Reminders", desc: "Add to cart and remind about abandoned carts" },
  { id: "lead_capture", label: "Lead Capture", desc: "Collect contact info and qualify prospects" },
  { id: "appointment_booking", label: "Appointment Booking", desc: "Schedule and confirm appointments" },
  { id: "order_tracking", label: "Order Tracking & Status", desc: "Update shoppers on their orders" },
  { id: "multilingual_support", label: "Multilingual Support", desc: "Serve shoppers in their preferred language" },
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
  retell_agent_id: string | null;
  handoff_enabled?: boolean;
  handoff_phone?: string | null;
  handoff_email?: string | null;
  handoff_message?: string;
  widget_config?: Record<string, any>;
  supported_languages: string[];
  primary_goals: string[];
  escalation_email: string;
  response_length: "brief" | "moderate" | "detailed";
  [key: string]: any;
}

interface PhoneNumberRecord {
  id: string;
  phone_number: string;
  friendly_name: string;
  is_active: boolean;
  mode?: string;
  forward_to?: string;
}

interface AvailableNumber {
  phone_number: string;
  friendly_name: string;
  location?: string;
  capabilities?: { voice?: boolean; sms?: boolean };
  monthly_rate?: number;
}

type AgentConfigTab = "personality" | "voice" | "brain" | "languages" | "knowledge" | "telephony" | "widget" | "test";

export function AgentConfigPage({ initialTab = "personality" }: { initialTab?: AgentConfigTab }) {
  const { user } = useAuth();
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [widget, setWidget] = useState<WidgetEmbedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<AgentConfigTab>(initialTab);
  const [telephonyTestNumber, setTelephonyTestNumber] = useState("");
  const [telephonyCalling, setTelephonyCalling] = useState(false);
  const [telephonyMessage, setTelephonyMessage] = useState("");
  const [telephonyNumbers, setTelephonyNumbers] = useState<PhoneNumberRecord[]>([]);
  const [telephonyNumbersLoading, setTelephonyNumbersLoading] = useState(false);
  const [telephonyAreaCode, setTelephonyAreaCode] = useState("");
  const [telephonyNumberType, setTelephonyNumberType] = useState<"local" | "toll_free">("local");
  const [telephonySearchResults, setTelephonySearchResults] = useState<AvailableNumber[]>([]);
  const [telephonySearching, setTelephonySearching] = useState(false);
  const [telephonyNumberError, setTelephonyNumberError] = useState("");
  const [telephonyNumberMessage, setTelephonyNumberMessage] = useState("");
  const [telephonyBuyingNumber, setTelephonyBuyingNumber] = useState<string | null>(null);
  const [telephonyBuyTarget, setTelephonyBuyTarget] = useState<AvailableNumber | null>(null);
  const [agreedToPolicy, setAgreedToPolicy] = useState(() => {
    try { return localStorage.getItem("omniweb_policy_agreed") === "1"; } catch { return false; }
  });

  // Language search filter
  const [langSearch, setLangSearch] = useState("");

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

  const loadTelephonyNumbers = useCallback(async () => {
    setTelephonyNumbersLoading(true);
    setTelephonyNumberError("");
    try {
      const res = await getNumbers();
      setTelephonyNumbers(res.numbers || res || []);
    } catch (err: any) {
      setTelephonyNumberError(err.message || "Failed to load phone numbers");
    } finally {
      setTelephonyNumbersLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  useEffect(() => {
    if (activeTab === "knowledge") loadKbDocs();
  }, [activeTab, loadKbDocs]);

  useEffect(() => {
    if (activeTab === "telephony") loadTelephonyNumbers();
  }, [activeTab, loadTelephonyNumbers]);

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
        primary_goals: config.primary_goals,
        escalation_email: config.escalation_email,
        handoff_enabled: config.handoff_enabled,
        handoff_phone: config.handoff_phone,
        handoff_email: config.handoff_email || config.escalation_email,
        handoff_message: config.handoff_message,
        widget_config: config.widget_config,
        response_length: config.response_length,
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

  const updateTelephonyWidget = (field: string, value: any) => {
    if (!config) return;
    const nextWidget = {
      ...(config.widget_config || {}),
      ai_telephony: {
        ...((config.widget_config || {}).ai_telephony || {}),
        [field]: value,
      },
    };
    update("widget_config", nextWidget);
  };

  const selectTelephonyNumber = (phoneNumber: string) => {
    updateTelephonyWidget("phone_number", phoneNumber);
    setTelephonyNumberMessage(`${formatPhone(phoneNumber)} selected for AI Telephony. Save & Deploy to publish it.`);
    setTelephonyNumberError("");
  };

  const handleTelephonyNumberSearch = async () => {
    setTelephonySearching(true);
    setTelephonyNumberError("");
    setTelephonyNumberMessage("");
    setTelephonySearchResults([]);
    setTelephonyBuyTarget(null);
    try {
      const res = await searchAvailableNumbers(
        telephonyAreaCode || undefined,
        "US",
        12,
        telephonyNumberType,
      );
      const numbers = res.numbers || [];
      setTelephonySearchResults(numbers);
      if (numbers.length === 0) {
        setTelephonyNumberError("No numbers found. Try a different area code.");
      }
    } catch (err: any) {
      setTelephonyNumberError(err.message || "Could not search available numbers");
    } finally {
      setTelephonySearching(false);
    }
  };

  const handleTelephonyNumberBuy = async () => {
    if (!telephonyBuyTarget) return;
    setTelephonyBuyingNumber(telephonyBuyTarget.phone_number);
    setTelephonyNumberError("");
    setTelephonyNumberMessage("");
    try {
      const friendlyName = telephonyBuyTarget.friendly_name || "Omniweb AI Phone Line";
      const purchased = await buyNumber(telephonyBuyTarget.phone_number, friendlyName);
      const phoneNumber = purchased.phone_number || telephonyBuyTarget.phone_number;
      selectTelephonyNumber(phoneNumber);
      setTelephonySearchResults((prev) => prev.filter((n) => n.phone_number !== phoneNumber));
      setTelephonyBuyTarget(null);
      await loadTelephonyNumbers();
    } catch (err: any) {
      setTelephonyNumberError(err.message || "Could not buy this phone number");
    } finally {
      setTelephonyBuyingNumber(null);
    }
  };

  const handleTelephonyTestCall = async () => {
    if (!config || !clientId || !telephonyTestNumber.trim()) return;
    setTelephonyCalling(true);
    setTelephonyMessage("");
    try {
      const res = await startRetellPhoneCall({
        clientId,
        toNumber: telephonyTestNumber,
        language: config.supported_languages?.[0] || "en",
      });
      setTelephonyMessage(`Calling ${res.to_number} now from ${res.from_number}.`);
    } catch (err: any) {
      setTelephonyMessage(err.message || "Could not start the Omniweb AI phone call.");
    } finally {
      setTelephonyCalling(false);
    }
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
    { id: "knowledge" as const, label: "Knowledge", icon: BookOpen },
    { id: "telephony" as const, label: "AI Telephony", icon: PhoneCall },
    { id: "widget" as const, label: "Embed", icon: Code },
    { id: "test" as const, label: "Test Agent", icon: Mic },
  ];

  return (
    <div className="w-full p-6">
      <div className="max-w-[860px] space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">AI Agent Configuration</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Customize your AI agent and get your embed code
          </p>
        </div>
        <div className="flex items-center gap-2">
          {config.retell_agent_id ? (
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
        <>
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
              <Textarea value={config.agent_greeting || ""} onChange={(e) => update("agent_greeting", e.target.value)} placeholder="Thank you for visiting our website today... it will be my pleasure to help you" rows={3} />
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
            <div className="space-y-1.5">
              <Label>Escalation Email</Label>
              <Input type="email" value={config.escalation_email || ""} onChange={(e) => update("escalation_email", e.target.value)} placeholder="human@yourbusiness.com" />
              <p className="text-xs text-muted-foreground">When a shopper needs human help, the agent will direct them here</p>
            </div>
            <div className="space-y-1.5">
              <Label>Response Length</Label>
              <div className="flex gap-2">
                {(["brief", "moderate", "detailed"] as const).map((len) => (
                  <button key={len} onClick={() => update("response_length", len)}
                    className={cn("flex-1 py-2 px-3 rounded-lg border text-sm font-medium capitalize transition-colors",
                      (config.response_length || "moderate") === len
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-border text-muted-foreground hover:border-muted-foreground/50")}>
                    {len}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Primary Goals */}
        <Card>
          <CardHeader>
            <CardTitle>Primary Goals</CardTitle>
            <CardDescription>Select what your AI agent should help shoppers with</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {PRIMARY_GOALS.map((goal) => {
              const isAll = goal.id === "all";
              const goals = config.primary_goals ?? PRIMARY_GOALS.map(g => g.id);
              const allSelected = PRIMARY_GOALS.filter(g => g.id !== "all").every(g => goals.includes(g.id));
              const checked = isAll ? allSelected : goals.includes(goal.id);
              return (
                <label key={goal.id} className={cn(
                  "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                  checked ? "border-primary/40 bg-primary/5" : "border-border hover:bg-secondary/40"
                )}>
                  <input type="checkbox" checked={checked} className="mt-0.5 accent-primary"
                    onChange={() => {
                      const current = config.primary_goals ?? PRIMARY_GOALS.map(g => g.id);
                      if (isAll) {
                        update("primary_goals", allSelected ? [] : PRIMARY_GOALS.map(g => g.id));
                      } else {
                        const next = checked ? current.filter((id: string) => id !== goal.id) : [...current, goal.id];
                        update("primary_goals", next);
                      }
                    }} />
                  <div className="min-w-0">
                    <p className={cn("text-sm font-medium", isAll && "font-bold")}>{goal.label}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{goal.desc}</p>
                  </div>
                </label>
              );
            })}
          </CardContent>
        </Card>

        {/* Financial Policy Notice */}
        <Card className="border-amber-500/30 bg-amber-500/[0.04]">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="shrink-0 mt-0.5 p-1.5 rounded-lg bg-amber-500/15">
                <Zap className="w-4 h-4 text-amber-500" />
              </div>
              <div className="space-y-2">
                <p className="text-sm font-semibold text-foreground">AI Agent Financial Policy</p>
                <div className="text-xs text-muted-foreground space-y-1.5">
                  <p className="flex items-center gap-2"><span className="text-emerald-500 font-bold">✓</span> Agent CAN add products to the shopper&apos;s cart</p>
                  <p className="flex items-center gap-2"><span className="text-emerald-500 font-bold">✓</span> Agent CAN remind shoppers about abandoned carts</p>
                  <p className="flex items-center gap-2"><span className="text-red-400 font-bold">✗</span> Agent CANNOT process checkouts or complete payments</p>
                  <p className="flex items-center gap-2"><span className="text-red-400 font-bold">✗</span> Agent CANNOT issue refunds or access billing information</p>
                  <p className="flex items-center gap-2"><span className="text-red-400 font-bold">✗</span> Agent CANNOT handle any financial transactions</p>
                </div>
                <p className="text-xs text-amber-600 dark:text-amber-400 pt-1">
                  For any financial request, the agent will escalate to a human representative using your escalation email above.
                </p>
                <label className="flex items-center gap-2 mt-2 cursor-pointer">
                  <input type="checkbox" checked={agreedToPolicy}
                    className="accent-primary"
                    onChange={(e) => {
                      setAgreedToPolicy(e.target.checked);
                      try { localStorage.setItem("omniweb_policy_agreed", e.target.checked ? "1" : "0"); } catch {}
                    }} />
                  <span className="text-xs font-medium text-foreground">I understand and agree to these restrictions</span>
                </label>
              </div>
            </div>
          </CardContent>
        </Card>
        </>
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
              Choose which languages your AI agent can speak. The widget will show a language selector to shoppers with all enabled languages.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Quick actions + count */}
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">{config.supported_languages?.length ?? 1}</span> of {LANGUAGE_OPTIONS.length} languages enabled
              </p>
              <div className="flex gap-2">
                <button onClick={() => update("supported_languages", LANGUAGE_OPTIONS.map(l => l.code))} className="text-xs text-primary hover:underline font-medium">
                  Enable all
                </button>
                <span className="text-muted-foreground">·</span>
                <button onClick={() => update("supported_languages", ["en"])} className="text-xs text-muted-foreground hover:underline">
                  English only
                </button>
              </div>
            </div>

            {/* Search dropdown */}
            <div className="relative">
              <Input
                value={langSearch}
                onChange={(e) => setLangSearch(e.target.value)}
                placeholder="Search languages..."
                className="pr-8"
              />
              {langSearch && (
                <button onClick={() => setLangSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Language list */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-72 overflow-y-auto pr-1">
              {LANGUAGE_OPTIONS.filter(l =>
                !langSearch || l.label.toLowerCase().includes(langSearch.toLowerCase()) || l.code.toLowerCase().includes(langSearch.toLowerCase())
              ).map((lang) => {
                const enabled = config.supported_languages?.includes(lang.code) ?? lang.code === "en";
                const isEnglish = lang.code === "en";
                return (
                  <label
                    key={lang.code}
                    className={cn(
                      "flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-colors",
                      enabled ? "border-primary/40 bg-primary/5" : "border-border hover:bg-secondary/40",
                      isEnglish && "cursor-default"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={enabled}
                      disabled={isEnglish}
                      className="accent-primary shrink-0"
                      onChange={() => {
                        if (isEnglish) return;
                        const current = config.supported_languages ?? ["en"];
                        const next = enabled ? current.filter((c: string) => c !== lang.code) : [...current, lang.code];
                        update("supported_languages", next);
                      }}
                    />
                    <span className="text-base">{lang.flag}</span>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{lang.label}</div>
                      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{lang.code}</div>
                    </div>
                  </label>
                );
              })}
            </div>

            <p className="text-xs text-muted-foreground">
              English is always required. Voice mode uses Deepgram STT + ElevenLabs TTS for each selected language.
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
                        type="text"
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

      {activeTab === "telephony" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>AI Telephony</CardTitle>
              <CardDescription>
                Use the same Omniweb AI voice agent over the phone. Omniweb AI calls the customer from your configured number and can escalate to the owner&apos;s phone.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Omniweb AI phone agent ID</Label>
                  <Input
                    value={config.retell_agent_id || ""}
                    onChange={(e) => update("retell_agent_id", e.target.value)}
                    placeholder="agent_xxxxxxxxx"
                  />
                  <p className="text-xs text-muted-foreground">Telephony uses the same AI brain as your Omniweb voice agent.</p>
                </div>
                <div className="space-y-2">
                  <Label>AI telephone number</Label>
                  <Input
                    value={(config.widget_config?.ai_telephony?.phone_number as string) || ""}
                    onChange={(e) => updateTelephonyWidget("phone_number", e.target.value)}
                    placeholder="+15551234567"
                  />
                  <p className="text-xs text-muted-foreground">This is the Omniweb AI phone number customers see calls from.</p>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-secondary/30 p-4 space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-foreground">Get an Omniweb AI phone number</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Search and buy a local or toll-free number, then use it for AI Telephony.
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={loadTelephonyNumbers} disabled={telephonyNumbersLoading}>
                    {telephonyNumbersLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Refresh"}
                  </Button>
                </div>

                {telephonyNumberError && (
                  <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-400">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    <span>{telephonyNumberError}</span>
                  </div>
                )}
                {telephonyNumberMessage && (
                  <div className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 p-3 text-xs text-primary">
                    <Check className="w-3.5 h-3.5 shrink-0" />
                    <span>{telephonyNumberMessage}</span>
                  </div>
                )}

                {telephonyNumbers.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Your numbers</p>
                    <div className="grid md:grid-cols-2 gap-2">
                      {telephonyNumbers.map((num) => {
                        const selected = (config.widget_config?.ai_telephony?.phone_number as string) === num.phone_number;
                        return (
                          <button
                            key={num.id}
                            type="button"
                            onClick={() => selectTelephonyNumber(num.phone_number)}
                            className={cn(
                              "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                              selected
                                ? "border-primary/40 bg-primary/10"
                                : "border-border hover:border-primary/30 hover:bg-accent/30",
                            )}
                          >
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                              <Phone className="w-4 h-4 text-primary" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-mono text-sm font-semibold text-foreground">{formatPhone(num.phone_number)}</p>
                              <p className="truncate text-xs text-muted-foreground">{num.friendly_name || "Omniweb AI line"}</p>
                            </div>
                            {selected && <Badge variant="success">Selected</Badge>}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <div className="flex gap-1 p-0.5 bg-accent/50 rounded-lg w-fit">
                    <button
                      type="button"
                      onClick={() => setTelephonyNumberType("local")}
                      className={cn(
                        "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                        telephonyNumberType === "local"
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      Local
                    </button>
                    <button
                      type="button"
                      onClick={() => setTelephonyNumberType("toll_free")}
                      className={cn(
                        "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                        telephonyNumberType === "toll_free"
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      Toll-Free
                    </button>
                  </div>

                  <div className="flex gap-2">
                    <Input
                      placeholder={telephonyNumberType === "toll_free" ? "Area code, e.g. 800" : "Area code, e.g. 305"}
                      value={telephonyAreaCode}
                      onChange={(e) => setTelephonyAreaCode(e.target.value.replace(/\D/g, "").slice(0, 3))}
                      className="font-mono"
                    />
                    <Button onClick={handleTelephonyNumberSearch} disabled={telephonySearching}>
                      {telephonySearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      Search
                    </Button>
                  </div>

                  {telephonySearchResults.length > 0 && (
                    <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                      {telephonySearchResults.map((num) => {
                        const selected = telephonyBuyTarget?.phone_number === num.phone_number;
                        return (
                          <div
                            key={num.phone_number}
                            className={cn(
                              "flex items-center gap-3 rounded-lg border p-3",
                              selected ? "border-primary/40 bg-primary/10" : "border-border",
                            )}
                          >
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                              <Phone className="w-4 h-4 text-primary" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-mono text-sm font-semibold text-foreground">{formatPhone(num.phone_number)}</p>
                              {num.location && (
                                <p className="flex items-center gap-1 text-xs text-muted-foreground">
                                  <MapPin className="w-3 h-3" /> {num.location}
                                </p>
                              )}
                            </div>
                            {num.monthly_rate ? (
                              <span className="text-xs text-muted-foreground">${num.monthly_rate}/mo</span>
                            ) : null}
                            <Button
                              size="sm"
                              variant={selected ? "default" : "outline"}
                              onClick={() => setTelephonyBuyTarget(selected ? null : num)}
                              disabled={telephonyBuyingNumber === num.phone_number}
                            >
                              {telephonyBuyingNumber === num.phone_number ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : selected ? (
                                "Selected"
                              ) : (
                                "Select"
                              )}
                            </Button>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {telephonyBuyTarget && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/20 bg-primary/5 p-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">Buy {formatPhone(telephonyBuyTarget.phone_number)}</p>
                        <p className="text-xs text-muted-foreground">
                          This purchases the number and fills it into AI Telephony. Save & Deploy when done.
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button onClick={handleTelephonyNumberBuy} disabled={!!telephonyBuyingNumber} size="sm">
                          {telephonyBuyingNumber ? (
                            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Buying...</>
                          ) : (
                            <><Plus className="w-3.5 h-3.5" /> Buy Number</>
                          )}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setTelephonyBuyTarget(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Human escalation phone</Label>
                  <Input
                    value={config.handoff_phone || ""}
                    onChange={(e) => {
                      update("handoff_phone", e.target.value);
                      update("handoff_enabled", Boolean(e.target.value.trim()));
                    }}
                    placeholder="+15557654321"
                  />
                  <p className="text-xs text-muted-foreground">When the AI cannot handle something, it should transfer/escalate here.</p>
                </div>
                <div className="space-y-2">
                  <Label>Escalation email fallback</Label>
                  <Input
                    value={config.handoff_email || config.escalation_email || ""}
                    onChange={(e) => {
                      update("handoff_email", e.target.value);
                      update("escalation_email", e.target.value);
                    }}
                    placeholder="owner@example.com"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Escalation message</Label>
                <Textarea
                  value={config.handoff_message || ""}
                  onChange={(e) => update("handoff_message", e.target.value)}
                  rows={3}
                  placeholder="Let me connect you with a human who can help with this directly."
                />
              </div>

              <div className="rounded-xl border border-border bg-secondary/40 p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <PhoneCall className="w-4 h-4 text-primary" />
                  <h3 className="font-medium">Call Us widget preview</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  The storefront widget asks the visitor for their phone number, then Omniweb AI calls them and starts the AI conversation.
                </p>
                <div className="flex gap-2">
                  <Input
                    value={telephonyTestNumber}
                    onChange={(e) => setTelephonyTestNumber(e.target.value)}
                    placeholder="+15551234567"
                  />
                  <Button onClick={handleTelephonyTestCall} disabled={telephonyCalling || !telephonyTestNumber.trim()}>
                    {telephonyCalling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PhoneCall className="w-3.5 h-3.5" />}
                    Call me
                  </Button>
                </div>
                {telephonyMessage && (
                  <p className="text-xs text-muted-foreground">{telephonyMessage}</p>
                )}
              </div>

              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                Save & Deploy after editing. Human transfer uses the phone number and prompt context supplied on this page.
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "widget" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Agent Status</CardTitle>
              <CardDescription>
                {config.retell_agent_id ? "Your AI agent is live and ready" : "Add your Omniweb AI phone agent ID to go live"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {config.retell_agent_id ? (
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-sm font-medium text-green-500">Active</span>
                  <span className="text-xs text-muted-foreground ml-2 font-mono">{config.retell_agent_id}</span>
                  {/* Agent ID shown for debugging — brand name hidden */}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-sm">Add your Omniweb AI phone agent ID, save, then embed the script below</span>
                </div>
              )}
            </CardContent>
          </Card>

          {widget && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Voice Widget Embed</CardTitle>
                  <CardDescription>Add this iframe to your website for a voice-first assistant</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="relative">
                    <pre className="bg-secondary p-4 rounded-lg text-xs overflow-x-auto font-mono whitespace-pre-wrap">{widget.embed_code}</pre>
                    <Button size="sm" variant="outline" className="absolute top-2 right-2" onClick={() => copyToClipboard(widget.embed_code, "embed")}>
                      {copied === "embed" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">Paste this into your website HTML. The widget appears as a floating voice button in the bottom-right corner.</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Test Your Agent</CardTitle>
                  <CardDescription>Try your voice agent before deploying to your website</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex gap-2 flex-wrap">
                    {widget.widget_url && (
                      <Button size="sm" onClick={() => window.open(widget.widget_url!, "_blank")}>
                        <Mic className="w-3.5 h-3.5" />
                        Test Voice Widget
                      </Button>
                    )}
                    {widget.widget_url && (
                      <Button variant="outline" size="sm" onClick={() => copyToClipboard(widget.widget_url!, "url")}>
                        {copied === "url" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                        Copy Widget URL
                      </Button>
                    )}
                  </div>
                  {widget.widget_url && (
                    <div className="bg-secondary px-3 py-2 rounded-md text-xs text-muted-foreground font-mono break-all">{widget.widget_url}</div>
                  )}
                </CardContent>
              </Card>
            </>
          )}

          {!widget && !config.retell_agent_id && (
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
      {activeTab === "test" && (
        <div className="max-w-[480px]">
          <AgentVoiceTestPanel
            clientId={clientId}
            agentName={config.agent_name || "your agent"}
            widgetUrl={widget?.widget_url || (clientId ? `/widget/${encodeURIComponent(clientId)}?panel=1` : "")}
          />
        </div>
      )}
      </div>
    </div>
  );
}

type VoiceStatus = "idle" | "connecting" | "listening" | "text";

type VoiceBootstrapPayload = {
  websocket_url: string;
  access_token: string;
  settings: Record<string, unknown>;
};

function AgentVoiceTestPanel({
  clientId,
  agentName,
  widgetUrl,
}: {
  clientId: string;
  agentName: string;
  widgetUrl: string;
}) {
  const sessionRef = useRef<DeepgramVoiceAgentSession | null>(null);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [selectedLanguage, setSelectedLanguage] = useState("en");
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [textDraft, setTextDraft] = useState("");
  const [error, setError] = useState("");

  const sessionActive = status === "listening" || status === "text";

  const stopSession = useCallback(async () => {
    await sessionRef.current?.disconnect();
    sessionRef.current = null;
    setStatus("idle");
  }, []);

  useEffect(() => {
    return () => {
      void stopSession();
    };
  }, [stopSession]);

  const bootstrap = useCallback(async (): Promise<VoiceBootstrapPayload> => {
    const res = await fetch("/api/chat/voice-agent/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: clientId,
        language: selectedLanguage,
      }),
    });

    if (!res.ok) {
      const raw = await res.text();
      let message = raw || `HTTP ${res.status}`;
      try {
        const parsed = JSON.parse(raw) as { detail?: unknown };
        if (parsed.detail) {
          message = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
        }
      } catch {
        /* keep raw body */
      }
      throw new Error(message);
    }

    return (await res.json()) as VoiceBootstrapPayload;
  }, [clientId, selectedLanguage]);

  const startSession = useCallback(
    async (mode: "voice" | "text") => {
      if (!clientId) {
        setError("No client ID is available for this demo account.");
        return;
      }

      setError("");
      setStatus("connecting");
      try {
        await stopSession();
        const payload = await bootstrap();
        const session = new DeepgramVoiceAgentSession({
          onTranscript: (line) => setLines((prev) => [...prev, line]),
          onError: (message) => setError(message),
          onClose: () => setStatus("idle"),
        });
        sessionRef.current = session;
        await session.connect({
          websocketUrl: payload.websocket_url,
          accessToken: payload.access_token,
          settings: payload.settings,
          enableMic: mode === "voice",
        });
        setStatus(mode === "voice" ? "listening" : "text");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to connect to the agent.");
        await stopSession();
      }
    },
    [bootstrap, clientId, stopSession],
  );

  const sendText = useCallback(async () => {
    const message = textDraft.trim();
    if (!message) return;

    if (!sessionRef.current) {
      await startSession("text");
    }

    sessionRef.current?.injectUserMessage(message);
    setTextDraft("");
  }, [startSession, textDraft]);

  const statusLabel =
    status === "connecting"
      ? "Connecting..."
      : status === "listening"
        ? "Listening..."
        : status === "text"
          ? "Text chat active"
          : "Ready to test";

  const orbActive = status === "listening";

  return (
    <div className="overflow-hidden rounded-2xl border border-primary/20" style={{ background: "linear-gradient(180deg,#0f1120 0%,#0c0e1a 100%)" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className={cn("w-2 h-2 rounded-full", sessionActive ? "bg-emerald-400 shadow-[0_0_6px_rgba(74,222,128,0.7)]" : "bg-slate-600")} />
            <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
              {sessionActive ? "Live Session" : "Talk to Agent"}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {sessionActive && (
            <button
              onClick={() => void stopSession()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-red-500/30 bg-red-500/10 text-red-400 text-xs font-semibold hover:bg-red-500/20 transition-colors"
            >
              <Square className="h-3 w-3" />
              End
            </button>
          )}
          {widgetUrl && (
            <button
              onClick={() => window.open(widgetUrl, "_blank")}
              className="px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.04] text-slate-400 text-xs font-medium hover:bg-white/[0.08] transition-colors"
            >
              Full Page
            </button>
          )}
        </div>
      </div>

      {/* Orb area */}
      <div className="flex flex-col items-center justify-center py-8 gap-5" style={{ background: "radial-gradient(ellipse at 50% 0%,rgba(99,102,241,.12) 0%,transparent 65%)" }}>
        {/* Orb */}
        <div className="relative">
          {/* Glow ring */}
          {orbActive && (
            <div className="absolute inset-0 rounded-full animate-ping" style={{ background: "rgba(99,102,241,.15)", animationDuration: "2s" }} />
          )}
          <div
            className={cn("relative rounded-full transition-all duration-500", orbActive ? "scale-110" : "scale-100")}
            style={{
              width: 100,
              height: 100,
              background: "conic-gradient(from 180deg,#22d3ee,#818cf8,#a855f7,#ec4899,#f59e0b,#22d3ee)",
              boxShadow: orbActive
                ? "0 0 48px rgba(99,102,241,.55), 0 0 80px rgba(168,85,247,.25)"
                : "0 0 24px rgba(99,102,241,.2)",
            }}
          >
            <div
              className="absolute rounded-full"
              style={{ inset: 5, background: "radial-gradient(circle at 38% 32%,#1e1b4b 0%,#0c0e1a 70%)" }}
            />
            {/* Inner ring */}
            <div className="absolute rounded-full border border-white/10" style={{ inset: 8 }} />
          </div>
        </div>

        {/* Sound wave bars */}
        <div className="flex items-center gap-1 h-6">
          {[0.4, 0.7, 1, 0.65, 0.85, 0.5, 0.9].map((h, i) => (
            <div
              key={i}
              className="w-1 rounded-full transition-all duration-300"
              style={{
                height: orbActive ? `${h * 20}px` : "4px",
                background: orbActive
                  ? `hsl(${243 + i * 8}, 70%, ${55 + i * 3}%)`
                  : "rgba(100,116,139,0.4)",
                transitionDelay: orbActive ? `${i * 60}ms` : "0ms",
              }}
            />
          ))}
        </div>

        {/* Agent name + status */}
        <div className="text-center">
          <p className="text-sm font-bold text-slate-200">{agentName}</p>
          <p className="text-xs text-slate-500 mt-0.5">{statusLabel}</p>
        </div>

        {/* Main CTA */}
        <button
          disabled={status === "connecting"}
          onClick={() => void startSession("voice")}
          className={cn(
            "flex items-center gap-2.5 px-7 py-3 rounded-full font-bold text-sm transition-all duration-200",
            status === "connecting"
              ? "opacity-50 cursor-not-allowed bg-slate-700 text-slate-400"
              : orbActive
              ? "bg-gradient-to-r from-violet-600 to-indigo-500 text-white shadow-[0_4px_20px_rgba(99,102,241,.5)] hover:shadow-[0_6px_28px_rgba(99,102,241,.65)] hover:scale-105"
              : "bg-gradient-to-r from-indigo-600 to-violet-500 text-white shadow-[0_4px_20px_rgba(99,102,241,.4)] hover:shadow-[0_6px_28px_rgba(99,102,241,.6)] hover:scale-105"
          )}
        >
          {status === "connecting" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Mic className="h-4 w-4" />
          )}
          {status === "connecting" ? "Connecting..." : orbActive ? "Restart Voice" : "Talk to Agent"}
        </button>
      </div>

      {/* Language selector */}
      <div className="px-5 pb-3 pt-1">
        <select
          value={selectedLanguage}
          disabled={sessionActive || status === "connecting"}
          onChange={(event) => setSelectedLanguage(event.target.value)}
          className="w-full h-9 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-xs text-slate-300 font-medium focus:outline-none focus:border-primary/50 disabled:opacity-50"
        >
          {LANGUAGE_OPTIONS.map((language) => (
            <option key={language.code} value={language.code} className="bg-slate-900">
              {language.flag} {language.label}
            </option>
          ))}
        </select>
      </div>

      {/* Divider */}
      <div className="h-px bg-white/[0.06] mx-5" />

      {/* Error */}
      {error && (
        <div className="mx-5 mt-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Transcript */}
      <div className="mx-5 my-3 max-h-52 min-h-[80px] overflow-y-auto space-y-2 rounded-xl border border-white/[0.06] bg-black/20 p-3 scrollbar-thin">
        {lines.length === 0 ? (
          <p className="text-xs leading-relaxed text-slate-600">
            Start a voice session or type a message below. The transcript will appear here — confirm your agent speaks the right language, greeting, and follows your instructions.
          </p>
        ) : (
          lines.map((line, index) => (
            <div
              key={`${index}-${line.role}`}
              className={cn(
                "rounded-xl px-3 py-2 text-sm max-w-[88%]",
                line.role === "user"
                  ? "ml-auto bg-indigo-600/30 border border-indigo-500/20 text-indigo-100"
                  : "mr-auto bg-white/[0.04] border border-white/[0.06] text-slate-300"
              )}
            >
              <p className="mb-1 text-[9px] uppercase tracking-widest font-semibold opacity-50">
                {line.role === "user" ? "You" : agentName}
              </p>
              <p className="whitespace-pre-wrap break-words leading-relaxed">{line.content}</p>
            </div>
          ))
        )}
      </div>

      {/* Text input */}
      <div className="flex items-end gap-2 px-5 pb-5">
        <Textarea
          rows={2}
          value={textDraft}
          onChange={(event) => setTextDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void sendText();
            }
          }}
          placeholder="Type a test message..."
          className="resize-none bg-white/[0.04] border-white/10 text-slate-200 placeholder:text-slate-600 focus:border-primary/40 rounded-xl text-sm"
        />
        <Button
          className="h-10 w-10 shrink-0 rounded-full p-0 bg-gradient-to-br from-indigo-600 to-violet-600 shadow-[0_2px_12px_rgba(99,102,241,.4)] hover:shadow-[0_4px_18px_rgba(99,102,241,.6)] hover:scale-105 transition-all"
          disabled={status === "connecting" || !textDraft.trim()}
          onClick={() => void sendText()}
          aria-label="Send test message"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

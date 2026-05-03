"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  getAgentConfig,
  updateAgentConfig,
  getWidgetEmbedCode,
  getMeWorkspace,
} from "@/lib/api";
import {
  CheckCircle,
  Copy,
  Loader2,
  Save,
  Code2,
  AlertTriangle,
  Clock,
} from "lucide-react";

// ── Helpers ──────────────────────────────────────────────────────────────────

function TrialBanner({
  trialEndsAt,
  subscriptionStatus,
}: {
  trialEndsAt: string | null | undefined;
  subscriptionStatus: string | null | undefined;
}) {
  if (subscriptionStatus === "active") return null;

  if (!trialEndsAt) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-950/30 px-4 py-3 text-sm text-amber-300">
        <AlertTriangle className="w-4 h-4 shrink-0" />
        <span>
          No active subscription. Your widget is disabled. Please subscribe to
          enable it.
        </span>
      </div>
    );
  }

  const end = new Date(trialEndsAt);
  const now = new Date();
  const diffMs = end.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffMs <= 0) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-300">
        <AlertTriangle className="w-4 h-4 shrink-0" />
        <span>
          Your 7-day free trial has expired. The widget is now disabled. Subscribe to
          re-enable it.
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-cyan-500/20 bg-cyan-950/20 px-4 py-3 text-sm text-cyan-300">
      <Clock className="w-4 h-4 shrink-0" />
      <span>
        Free trial active — <strong>{diffDays} day{diffDays !== 1 ? "s" : ""}</strong>{" "}
        remaining. The widget will stop working after your trial ends unless you
        subscribe.
      </span>
    </div>
  );
}

function SnippetModal({
  snippet,
  scriptUrl,
  publicWidgetKey,
  gtmInstructions,
  onCopied,
  onClose,
}: {
  snippet: string;
  scriptUrl: string;
  publicWidgetKey: string;
  gtmInstructions: string[];
  onCopied: () => void;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"snippet" | "gtm">("snippet");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      onCopied();
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl rounded-2xl border border-white/10 bg-slate-900 shadow-2xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1">Install Widget</h2>
        <p className="text-sm text-slate-400 mb-4">
          Use the same Omniweb script everywhere: paste it into your website, or
          install it through Google Tag Manager.
        </p>

        <div className="mb-4 grid grid-cols-2 gap-2 rounded-xl border border-white/10 bg-black/30 p-1">
          <button
            type="button"
            onClick={() => setActiveTab("snippet")}
            className={`rounded-lg px-3 py-2 text-sm transition-colors ${
              activeTab === "snippet"
                ? "bg-cyan-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Code snippet
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("gtm")}
            className={`rounded-lg px-3 py-2 text-sm transition-colors ${
              activeTab === "gtm"
                ? "bg-cyan-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Google Tag Manager
          </button>
        </div>

        {activeTab === "snippet" ? (
          <>
            <p className="mb-3 text-sm text-slate-400">
              Paste this before the closing{" "}
              <code className="rounded bg-black/40 px-1 text-xs text-cyan-300">
                &lt;/body&gt;
              </code>{" "}
              tag on every page where the assistant should appear.
            </p>
            <div className="relative mb-4 overflow-hidden rounded-xl border border-white/10 bg-black/60">
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all p-4 pr-24 text-xs text-cyan-200">
                {snippet}
              </pre>
              <button
                onClick={copy}
                className="absolute right-3 top-3 flex items-center gap-1.5 rounded-lg border border-white/10 bg-slate-800 px-3 py-1.5 text-xs text-white transition-colors hover:bg-slate-700"
              >
                {copied ? (
                  <>
                    <CheckCircle className="h-3.5 w-3.5 text-green-400" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    Copy
                  </>
                )}
              </button>
            </div>
          </>
        ) : (
          <div className="mb-4 space-y-4">
            <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-300">
              {gtmInstructions.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <div className="rounded-xl border border-white/10 bg-black/40 p-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                Custom HTML tag content
              </p>
              <pre className="whitespace-pre-wrap break-all text-xs text-cyan-200">
                {snippet}
              </pre>
            </div>
          </div>
        )}

        <div className="mb-4 grid gap-2 rounded-xl border border-white/10 bg-slate-950/70 p-4 text-xs text-slate-400 sm:grid-cols-2">
          <div>
            <span className="block text-slate-500">Public widget key</span>
            <span className="font-mono text-slate-200">{publicWidgetKey}</span>
          </div>
          <div>
            <span className="block text-slate-500">Script URL</span>
            <a
              href={scriptUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="break-all text-cyan-400 hover:text-cyan-300"
            >
              {scriptUrl}
            </a>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="rounded-xl border border-white/10 px-5 py-2 text-sm text-slate-300 hover:text-white hover:border-white/30 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Field helpers ─────────────────────────────────────────────────────────────

function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-slate-200">{label}</label>
      {children}
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className="rounded-xl border border-white/10 bg-slate-950/80 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 disabled:opacity-50"
    />
  );
}

function TextArea({
  value,
  onChange,
  placeholder,
  rows = 4,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      disabled={disabled}
      className="rounded-xl border border-white/10 bg-slate-950/80 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 resize-y disabled:opacity-50"
    />
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

interface ConfigState {
  agent_name: string;
  agent_greeting: string;
  business_name: string;
  business_type: string;
  website_domain: string;
  booking_url: string;
  timezone: string;
  tone: string;
  system_prompt: string;
  custom_context: string;
  after_hours_message: string;
  services: string; // comma-separated in UI
}

const DEFAULTS: ConfigState = {
  agent_name: "Alex",
  agent_greeting: "Thank you for visiting! How can I assist you today?",
  business_name: "",
  business_type: "",
  website_domain: "",
  booking_url: "",
  timezone: "America/New_York",
  tone: "professional",
  system_prompt: "",
  custom_context: "",
  after_hours_message:
    "We're currently closed but will call you back first thing in the morning.",
  services: "",
};

export default function AgentConfigPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [config, setConfig] = useState<ConfigState>(DEFAULTS);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(true);

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [snippetLoading, setSnippetLoading] = useState(false);
  const [snippetData, setSnippetData] = useState<{
    embed_snippet: string;
    public_widget_key: string;
    script_url: string;
    gtm_instructions: string[];
  } | null>(null);
  const [showSnippet, setShowSnippet] = useState(false);

  const [trialEndsAt, setTrialEndsAt] = useState<string | null>(null);
  const [subscriptionStatus, setSubscriptionStatus] = useState<string | null>(null);
  const [showCopyToast, setShowCopyToast] = useState(false);

  const saveSuccessTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copyToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const snippetCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/sign-in");
    }
  }, [authLoading, user, router]);

  // Load config + trial info
  useEffect(() => {
    if (!user) return;
    const clientId = user.client_id;

    async function load() {
      setLoadingConfig(true);
      setLoadError(null);
      try {
        const [cfg, ws] = await Promise.all([
          getAgentConfig(clientId),
          getMeWorkspace().catch(() => null),
        ]);

        setConfig({
          agent_name: cfg.agent_name ?? DEFAULTS.agent_name,
          agent_greeting: cfg.agent_greeting ?? DEFAULTS.agent_greeting,
          business_name: cfg.business_name ?? "",
          business_type: cfg.business_type ?? "",
          website_domain: cfg.website_domain ?? "",
          booking_url: cfg.booking_url ?? "",
          timezone: cfg.timezone ?? "America/New_York",
          tone: cfg.tone ?? "professional",
          system_prompt: cfg.system_prompt ?? "",
          custom_context: cfg.custom_context ?? "",
          after_hours_message: cfg.after_hours_message ?? DEFAULTS.after_hours_message,
          services: Array.isArray(cfg.services) ? cfg.services.join(", ") : "",
        });

        if (ws?.trial) {
          setTrialEndsAt(ws.trial.trial_ends_at ?? null);
          setSubscriptionStatus(ws.trial.subscription_status ?? null);
        }
      } catch (err: any) {
        setLoadError(err?.message ?? "Failed to load configuration");
      } finally {
        setLoadingConfig(false);
      }
    }

    load();
  }, [user]);

  const handleSave = useCallback(async () => {
    if (!user) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    const services = config.services
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      await updateAgentConfig(user.client_id, {
        agent_name: config.agent_name || undefined,
        agent_greeting: config.agent_greeting || undefined,
        business_name: config.business_name || undefined,
        business_type: config.business_type || undefined,
        website_domain: config.website_domain || undefined,
        booking_url: config.booking_url || undefined,
        timezone: config.timezone || undefined,
        tone: config.tone || undefined,
        system_prompt: config.system_prompt || undefined,
        custom_context: config.custom_context || undefined,
        after_hours_message: config.after_hours_message || undefined,
        services: services.length ? services : undefined,
      });
      setSaveSuccess(true);
      if (saveSuccessTimer.current) clearTimeout(saveSuccessTimer.current);
      saveSuccessTimer.current = setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setSaveError(err?.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  }, [user, config]);

  const handleGetSnippet = useCallback(async () => {
    if (!user) return;
    setSnippetLoading(true);
    try {
      const data = await getWidgetEmbedCode();
      setSnippetData({
        embed_snippet: data.embed_snippet,
        public_widget_key: data.public_widget_key,
        script_url: data.script_url,
        gtm_instructions:
          data.gtm_instructions && data.gtm_instructions.length
            ? data.gtm_instructions
            : [
                "Create a new Google Tag Manager Custom HTML tag.",
                "Paste the Omniweb script snippet into the tag.",
                "Set the trigger to All Pages, then submit and publish.",
              ],
      });
      setShowSnippet(true);
    } catch (err: any) {
      setSaveError(err?.message ?? "Failed to get snippet");
    } finally {
      setSnippetLoading(false);
    }
  }, [user]);

  const handleSnippetCopied = useCallback(() => {
    setShowCopyToast(true);
    if (copyToastTimer.current) {
      clearTimeout(copyToastTimer.current);
    }
    copyToastTimer.current = setTimeout(() => setShowCopyToast(false), 2400);

    if (snippetCloseTimer.current) {
      clearTimeout(snippetCloseTimer.current);
    }
    snippetCloseTimer.current = setTimeout(() => setShowSnippet(false), 1000);
  }, []);

  useEffect(() => {
    return () => {
      if (saveSuccessTimer.current) {
        clearTimeout(saveSuccessTimer.current);
      }
      if (copyToastTimer.current) {
        clearTimeout(copyToastTimer.current);
      }
      if (snippetCloseTimer.current) {
        clearTimeout(snippetCloseTimer.current);
      }
    };
  }, []);

  const set = (key: keyof ConfigState) => (val: string) =>
    setConfig((prev) => ({ ...prev, [key]: val }));

  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
        {/* Header */}
        <div className="mb-8">
          <p className="text-xs font-medium uppercase tracking-widest text-cyan-400/90 mb-2">
            Omniweb · Agent
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Agent Configuration
          </h1>
          <p className="mt-2 text-slate-400 text-sm leading-relaxed">
            Customize your AI agent's identity, voice, and business context.
            Changes are saved immediately and take effect on the next session.
          </p>
        </div>

        {/* Trial banner */}
        <div className="mb-6">
          <TrialBanner
            trialEndsAt={trialEndsAt}
            subscriptionStatus={subscriptionStatus}
          />
        </div>

        {loadingConfig ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : loadError ? (
          <div className="rounded-xl border border-red-500/30 bg-red-950/30 px-5 py-4 text-sm text-red-300">
            {loadError}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Identity card */}
            <section className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 space-y-5">
              <h2 className="text-base font-semibold text-white">Agent Identity</h2>

              <Field label="Agent Name">
                <TextInput
                  value={config.agent_name}
                  onChange={set("agent_name")}
                  placeholder="Alex"
                />
              </Field>

              <Field
                label="Greeting Message"
                hint="What your agent says when a conversation starts."
              >
                <TextArea
                  value={config.agent_greeting}
                  onChange={set("agent_greeting")}
                  placeholder="Thank you for visiting! How can I assist you today?"
                  rows={2}
                />
              </Field>

              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Tone">
                  <select
                    value={config.tone}
                    onChange={(e) => set("tone")(e.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-4 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
                  >
                    {["professional", "friendly", "formal", "casual", "empathetic"].map(
                      (t) => (
                        <option key={t} value={t}>
                          {t.charAt(0).toUpperCase() + t.slice(1)}
                        </option>
                      )
                    )}
                  </select>
                </Field>

                <Field label="Timezone">
                  <TextInput
                    value={config.timezone}
                    onChange={set("timezone")}
                    placeholder="America/New_York"
                  />
                </Field>
              </div>
            </section>

            {/* Business context card */}
            <section className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 space-y-5">
              <h2 className="text-base font-semibold text-white">Business Context</h2>

              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Business Name">
                  <TextInput
                    value={config.business_name}
                    onChange={set("business_name")}
                    placeholder="Acme Corp"
                  />
                </Field>

                <Field label="Business Type">
                  <TextInput
                    value={config.business_type}
                    onChange={set("business_type")}
                    placeholder="e.g. roofing, law firm, e-commerce"
                  />
                </Field>
              </div>

              <Field
                label="Website Domain"
                hint="Used for domain-locking your embed snippet."
              >
                <TextInput
                  value={config.website_domain}
                  onChange={set("website_domain")}
                  placeholder="example.com"
                />
              </Field>

              <Field label="Booking / Appointment URL">
                <TextInput
                  value={config.booking_url}
                  onChange={set("booking_url")}
                  placeholder="https://cal.com/your-link"
                />
              </Field>

              <Field
                label="Services Offered"
                hint="Comma-separated list of services (e.g. oil change, brake repair)."
              >
                <TextInput
                  value={config.services}
                  onChange={set("services")}
                  placeholder="oil change, brake repair, tire rotation"
                />
              </Field>
            </section>

            {/* Prompt card */}
            <section className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 space-y-5">
              <h2 className="text-base font-semibold text-white">Prompt & Instructions</h2>

              <Field
                label="Custom Instructions"
                hint="Additional rules or context for your agent beyond defaults."
              >
                <TextArea
                  value={config.custom_context}
                  onChange={set("custom_context")}
                  placeholder="e.g. Always ask for the caller's name first. Never discuss competitor pricing."
                  rows={4}
                />
              </Field>

              <Field
                label="After-Hours Message"
                hint="Shown to callers outside business hours."
              >
                <TextArea
                  value={config.after_hours_message}
                  onChange={set("after_hours_message")}
                  rows={2}
                />
              </Field>
            </section>

            {/* Action row */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:pointer-events-none px-6 py-2.5 text-sm font-medium text-white transition-colors"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : saveSuccess ? (
                  <CheckCircle className="w-4 h-4 text-green-300" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                {saving ? "Saving…" : saveSuccess ? "Saved!" : "Save configuration"}
              </button>

              <button
                onClick={handleGetSnippet}
                disabled={snippetLoading}
                className="flex items-center gap-2 rounded-xl border border-white/10 hover:border-white/30 bg-slate-800/60 hover:bg-slate-700/60 disabled:opacity-50 disabled:pointer-events-none px-6 py-2.5 text-sm font-medium text-white transition-colors"
              >
                {snippetLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Code2 className="w-4 h-4" />
                )}
                {snippetLoading ? "Loading…" : "Install snippet"}
              </button>
            </div>

            {saveError && (
              <div className="rounded-xl border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-300">
                {saveError}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Snippet modal */}
      {showSnippet && snippetData && (
        <SnippetModal
          snippet={snippetData.embed_snippet}
          scriptUrl={snippetData.script_url}
          publicWidgetKey={snippetData.public_widget_key}
          gtmInstructions={snippetData.gtm_instructions}
          onCopied={handleSnippetCopied}
          onClose={() => setShowSnippet(false)}
        />
      )}

      {showCopyToast && (
        <div className="fixed bottom-5 right-5 z-[60] rounded-xl border border-emerald-500/30 bg-emerald-950/80 px-4 py-3 text-sm text-emerald-200 shadow-2xl backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-300" />
            Snippet copied to clipboard.
          </div>
        </div>
      )}
    </div>
  );
}

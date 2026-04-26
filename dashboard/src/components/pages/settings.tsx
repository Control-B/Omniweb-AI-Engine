"use client";

import { useState, useEffect } from "react";
import {
  Building2,
  Key,
  Bell,
  CreditCard,
  Globe,
  Copy,
  Check,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  AlertTriangle,
  Trash2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  getProfile,
  updateProfile,
  changePassword,
  generateApiKey,
  parseJwt,
  getToken,
  deleteAccount,
  logout,
  type Profile,
} from "@/lib/api";

const TABS = ["profile", "api-keys", "notifications", "pricing"] as const;
type Tab = (typeof TABS)[number];

const ICON_MAP: Record<Tab, React.ElementType> = {
  profile: Building2,
  "api-keys": Key,
  notifications: Bell,
  pricing: CreditCard,
};

const TAB_LABELS: Record<Tab, string> = {
  profile: "Profile",
  "api-keys": "API Keys",
  notifications: "Notifications",
  pricing: "Pricing",
};

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="p-1 rounded hover:bg-accent"
    >
      {copied ? (
        <Check className="w-3.5 h-3.5 text-emerald-400" />
      ) : (
        <Copy className="w-3.5 h-3.5 text-muted-foreground" />
      )}
    </button>
  );
}

function RevealKey({ value }: { value: string }) {
  const [visible, setVisible] = useState(false);
  const masked = value.slice(0, 12) + "•".repeat(Math.max(0, value.length - 12));
  return (
    <div className="flex items-center gap-2 font-mono text-sm">
      <span className="select-all break-all">{visible ? value : masked}</span>
      <button onClick={() => setVisible(!visible)} className="p-1 rounded hover:bg-accent shrink-0">
        {visible ? (
          <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
        ) : (
          <Eye className="w-3.5 h-3.5 text-muted-foreground" />
        )}
      </button>
      <CopyButton value={value} />
    </div>
  );
}

/* ─── Profile Tab ─── */
function ProfileSettings() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [form, setForm] = useState({ name: "", businessName: "", notificationEmail: "", webhookUrl: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Password change
  const [pwForm, setPwForm] = useState({ current: "", newPw: "", confirm: "" });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p);
        setForm({
          name: p.name || "",
          businessName: p.business_name || "",
          notificationEmail: p.notification_email || "",
          webhookUrl: p.crm_webhook_url || "",
        });
      })
      .catch(() => setMsg({ type: "error", text: "Failed to load profile" }))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setMsg(null);
    try {
      const updated = await updateProfile({
        name: form.name,
        business_name: form.businessName,
        notification_email: form.notificationEmail,
        crm_webhook_url: form.webhookUrl,
      });
      setProfile(updated);
      setMsg({ type: "success", text: "Profile saved successfully" });
    } catch (err: any) {
      setMsg({ type: "error", text: err.message || "Failed to save" });
    } finally {
      setSaving(false);
    }
  }

  async function handlePasswordChange() {
    setPwMsg(null);
    if (pwForm.newPw !== pwForm.confirm) {
      setPwMsg({ type: "error", text: "New passwords do not match" });
      return;
    }
    if (pwForm.newPw.length < 6) {
      setPwMsg({ type: "error", text: "Password must be at least 6 characters" });
      return;
    }
    setPwSaving(true);
    try {
      await changePassword(pwForm.current, pwForm.newPw);
      setPwMsg({ type: "success", text: "Password changed successfully" });
      setPwForm({ current: "", newPw: "", confirm: "" });
    } catch (err: any) {
      setPwMsg({ type: "error", text: err.message || "Failed to change password" });
    } finally {
      setPwSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Business Info</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Your Name</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Business Name</Label>
            <Input
              value={form.businessName}
              onChange={(e) => setForm({ ...form, businessName: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Email</Label>
            <div className="p-2.5 rounded-lg bg-accent/50 border text-sm text-muted-foreground">
              {profile?.email}
            </div>
            <p className="text-[11px] text-muted-foreground">Contact support to change your email</p>
          </div>
          <div className="space-y-1.5">
            <Label>Notification Email</Label>
            <Input
              value={form.notificationEmail}
              onChange={(e) => setForm({ ...form, notificationEmail: e.target.value })}
              placeholder={profile?.email || "you@company.com"}
            />
            <p className="text-[11px] text-muted-foreground">Alerts will be sent here (defaults to account email)</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integrations</CardTitle>
          <CardDescription>
            Set up webhooks to push lead data to your CRM automatically
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>CRM Webhook URL</Label>
            <div className="flex gap-2">
              <Input
                value={form.webhookUrl}
                onChange={(e) => setForm({ ...form, webhookUrl: e.target.value })}
                placeholder="https://your-crm.com/api/leads"
              />
              <Button variant="outline" size="sm" className="shrink-0">
                <Globe className="w-3.5 h-3.5" />
                Test
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              We&apos;ll POST lead data here after every qualifying call
            </p>
          </div>
        </CardContent>
      </Card>

      {msg && (
        <div
          className={cn(
            "text-sm rounded-lg px-3 py-2 border",
            msg.type === "success"
              ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
              : "text-red-400 bg-red-500/10 border-red-500/20"
          )}
        >
          {msg.text}
        </div>
      )}

      <Button size="sm" onClick={handleSave} disabled={saving}>
        {saving && <Loader2 className="w-4 h-4 animate-spin" />}
        Save Changes
      </Button>

      {/* Password change section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Change Password
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Current Password</Label>
            <Input
              type="password"
              value={pwForm.current}
              onChange={(e) => setPwForm({ ...pwForm, current: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label>New Password</Label>
            <Input
              type="password"
              value={pwForm.newPw}
              onChange={(e) => setPwForm({ ...pwForm, newPw: e.target.value })}
              minLength={6}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Confirm New Password</Label>
            <Input
              type="password"
              value={pwForm.confirm}
              onChange={(e) => setPwForm({ ...pwForm, confirm: e.target.value })}
              minLength={6}
            />
          </div>
          {pwMsg && (
            <div
              className={cn(
                "text-sm rounded-lg px-3 py-2 border",
                pwMsg.type === "success"
                  ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                  : "text-red-400 bg-red-500/10 border-red-500/20"
              )}
            >
              {pwMsg.text}
            </div>
          )}
          <Button size="sm" variant="outline" onClick={handlePasswordChange} disabled={pwSaving}>
            {pwSaving && <Loader2 className="w-4 h-4 animate-spin" />}
            Update Password
          </Button>
        </CardContent>
      </Card>

      <DangerZone />
    </div>
  );
}

function DangerZone() {
  const [confirming, setConfirming] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  const handleDelete = async () => {
    setDeleting(true);
    setError("");
    try {
      await deleteAccount();
      logout();
    } catch (err: any) {
      setError(err.message || "Failed to delete account");
      setDeleting(false);
    }
  };

  return (
    <Card className="border-destructive/30">
      <CardHeader>
        <CardTitle className="text-destructive flex items-center gap-2">
          <Trash2 className="w-4 h-4" />
          Delete Account
        </CardTitle>
        <CardDescription>
          Permanently delete your account and all data including your AI agent,
          calls, leads, and phone numbers. This cannot be undone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!confirming ? (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setConfirming(true)}
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete My Account
          </Button>
        ) : (
          <div className="space-y-3">
            <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <p>
                This will permanently delete your account, AI agent, all call
                records, leads, and phone numbers. Type{" "}
                <strong>delete my account</strong> to confirm.
              </p>
            </div>
            <Input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="Type: delete my account"
            />
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="sm"
                disabled={confirmText !== "delete my account" || deleting}
                onClick={handleDelete}
              >
                {deleting && <Loader2 className="w-4 h-4 animate-spin" />}
                {deleting ? "Deleting..." : "Permanently Delete"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setConfirming(false);
                  setConfirmText("");
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ─── API Keys Tab ─── */
function ApiKeysSettings() {
  const [clientId, setClientId] = useState<string>("");
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [confirmRegen, setConfirmRegen] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (token) {
      const payload = parseJwt(token);
      if (payload?.sub) setClientId(payload.sub);
    }
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const result = await generateApiKey();
      setApiKey(result.api_key);
      setConfirmRegen(false);
    } catch {
      // error handled in apiFetch
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>API Credentials</CardTitle>
          <CardDescription>
            Use these credentials to connect external integrations to the Omniweb API
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1.5">
            <Label>Client ID</Label>
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent/50 border">
              <span className="font-mono text-sm select-all break-all">
                {clientId || "—"}
              </span>
              {clientId && <CopyButton value={clientId} />}
            </div>
          </div>
          {apiKey && (
            <div className="space-y-1.5">
              <Label>
                API Key{" "}
                <span className="text-amber-400 font-normal">(save now — shown only once)</span>
              </Label>
              <div className="p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/20">
                <RevealKey value={apiKey} />
              </div>
            </div>
          )}
          {!apiKey && (
            <div className="space-y-1.5">
              <Label>API Key</Label>
              <div className="p-2.5 rounded-lg bg-accent/50 border text-sm text-muted-foreground">
                Click &quot;Generate API Key&quot; below to create one
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-destructive/30">
        <CardHeader>
          <CardTitle className="text-destructive">
            {apiKey ? "Regenerate API Key" : "Generate API Key"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {confirmRegen ? (
            <div className="space-y-3">
              <div className="flex items-start gap-2 text-sm text-amber-400">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <p>This will revoke your current API key immediately. Any integrations using the old key will stop working.</p>
              </div>
              <div className="flex gap-2">
                <Button variant="destructive" size="sm" onClick={handleGenerate} disabled={generating}>
                  {generating && <Loader2 className="w-4 h-4 animate-spin" />}
                  Confirm
                </Button>
                <Button variant="outline" size="sm" onClick={() => setConfirmRegen(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">
                  {apiKey ? "Regenerate API Key" : "Generate API Key"}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {apiKey
                    ? "Current key will be revoked immediately"
                    : "Create an API key for external integrations"}
                </p>
              </div>
              <Button
                variant={apiKey ? "destructive" : "default"}
                size="sm"
                onClick={() => (apiKey ? setConfirmRegen(true) : handleGenerate())}
                disabled={generating}
              >
                {generating && <Loader2 className="w-4 h-4 animate-spin" />}
                {apiKey ? "Regenerate" : "Generate"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── Notifications Tab ─── */
function NotificationSettings() {
  const [prefs, setPrefs] = useState({
    missedCall: true,
    newLead: true,
    bookingConfirmed: true,
    weeklyReport: false,
    billingAlerts: true,
    smsChannel: true,
    emailChannel: true,
    webhookChannel: false,
  });

  const toggle = (key: keyof typeof prefs) =>
    setPrefs((p) => ({ ...p, [key]: !p[key] }));

  const Toggle = ({ checked, onChange }: { checked: boolean; onChange: () => void }) => (
    <button
      onClick={onChange}
      className={cn(
        "relative w-10 h-5.5 rounded-full transition-colors",
        checked ? "bg-primary" : "bg-muted-foreground/30"
      )}
      style={{ width: 40, height: 22 }}
    >
      <span
        className={cn(
          "absolute top-0.5 left-0.5 w-[18px] h-[18px] rounded-full bg-white transition-transform",
          checked && "translate-x-[18px]"
        )}
      />
    </button>
  );

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-2 text-sm text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
        <p>Notification preferences are saved locally for now. Email/SMS delivery coming soon.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Event Alerts</CardTitle>
          <CardDescription>Choose which events you want to be notified about</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {(
            [
              ["missedCall", "Missed Calls", "Get alerted when a call goes unanswered"],
              ["newLead", "New Leads", "Notification when the AI captures a qualified lead"],
              ["bookingConfirmed", "Booking Confirmed", "When a customer confirms an appointment"],
              ["weeklyReport", "Weekly Report", "Summary of calls, leads, and conversions"],
              ["billingAlerts", "Billing Alerts", "Subscription and usage notifications"],
            ] as const
          ).map(([key, title, desc]) => (
            <div key={key} className="flex items-center justify-between py-1">
              <div>
                <p className="text-sm font-medium text-foreground">{title}</p>
                <p className="text-[11px] text-muted-foreground">{desc}</p>
              </div>
              <Toggle checked={prefs[key]} onChange={() => toggle(key)} />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Channels</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {(
            [
              ["smsChannel", "SMS", "Text message alerts to your phone"],
              ["emailChannel", "Email", "Email notifications"],
              ["webhookChannel", "Webhook", "Push events to your CRM or custom endpoint"],
            ] as const
          ).map(([key, title, desc]) => (
            <div key={key} className="flex items-center justify-between py-1">
              <div>
                <p className="text-sm font-medium text-foreground">{title}</p>
                <p className="text-[11px] text-muted-foreground">{desc}</p>
              </div>
              <Toggle checked={prefs[key]} onChange={() => toggle(key)} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── Pricing Tab ─── */
const PRICING_PLANS = [
  {
    id: "starter",
    label: "Starter",
    price: "$149",
    period: "/mo",
    tagline: "Perfect for small businesses",
    color: "from-indigo-500/20 to-violet-500/10",
    border: "border-indigo-500/30",
    features: [
      "1 AI Agent",
      "500 conversations/mo",
      "Text + Voice modes",
      "10 languages",
      "Knowledge base (5 docs)",
      "Basic analytics",
      "Email support",
    ],
  },
  {
    id: "growth",
    label: "Growth",
    price: "$299",
    period: "/mo",
    tagline: "For growing stores & teams",
    color: "from-violet-500/20 to-purple-500/10",
    border: "border-violet-500/40",
    popular: true,
    features: [
      "3 AI Agents",
      "2,000 conversations/mo",
      "Text + Voice modes",
      "All 26 languages",
      "Knowledge base (unlimited docs)",
      "Advanced analytics + summaries",
      "Shopify native integration",
      "Priority support",
    ],
  },
  {
    id: "pro",
    label: "Pro",
    price: "$499",
    period: "/mo",
    tagline: "For high-volume & agencies",
    color: "from-emerald-500/20 to-teal-500/10",
    border: "border-emerald-500/30",
    features: [
      "Unlimited AI Agents",
      "Unlimited conversations",
      "Text + Voice modes",
      "All 26 languages",
      "Knowledge base (unlimited)",
      "Full analytics suite",
      "White-label widget",
      "Multi-store support",
      "Dedicated support",
      "Custom integrations",
    ],
  },
];

function PricingSettings() {
  const [plan, setPlan] = useState("starter");

  useEffect(() => {
    const token = getToken();
    if (token) {
      const payload = parseJwt(token);
      if (payload?.plan) setPlan(payload.plan);
    }
  }, []);

  return (
    <div className="space-y-6">
      {/* Current plan banner */}
      <div className="flex items-center gap-3 p-4 rounded-xl bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/20">
        <CreditCard className="w-5 h-5 text-primary shrink-0" />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-bold text-foreground capitalize">{plan} Plan</p>
            <Badge variant="success">Active</Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {PRICING_PLANS.find(p => p.id === plan)?.price ?? "—"}/mo ·{" "}
            {PRICING_PLANS.find(p => p.id === plan)?.tagline}
          </p>
        </div>
      </div>

      {/* Pricing cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PRICING_PLANS.map((p) => {
          const isCurrent = p.id === plan;
          return (
            <div
              key={p.id}
              className={cn(
                "relative rounded-2xl border p-5 space-y-4 bg-gradient-to-b transition-all",
                p.color, p.border,
                isCurrent && "ring-2 ring-primary ring-offset-2 ring-offset-background"
              )}
            >
              {p.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-violet-600 text-white shadow-lg">
                    Most Popular
                  </span>
                </div>
              )}
              <div>
                <p className="text-sm font-bold text-foreground">{p.label}</p>
                <p className="text-xs text-muted-foreground">{p.tagline}</p>
              </div>
              <div className="flex items-end gap-0.5">
                <span className="text-3xl font-extrabold text-foreground">{p.price}</span>
                <span className="text-sm text-muted-foreground mb-1">{p.period}</span>
              </div>
              <ul className="space-y-1.5">
                {p.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="text-emerald-500 font-bold shrink-0">✓</span> {f}
                  </li>
                ))}
              </ul>
              {isCurrent ? (
                <div className="w-full py-2 text-center rounded-lg bg-primary/10 text-primary text-xs font-semibold">
                  Current Plan
                </div>
              ) : (
                <a
                  href="mailto:support@omniweb.ai?subject=Plan Upgrade Request"
                  className="block w-full py-2 text-center rounded-lg bg-foreground text-background text-xs font-semibold hover:opacity-90 transition-opacity"
                >
                  Upgrade
                </a>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-xs text-muted-foreground text-center">
        To change your plan, contact us at{" "}
        <a href="mailto:support@omniweb.ai" className="text-primary hover:underline">support@omniweb.ai</a>
        . Self-service billing coming soon.
      </p>
    </div>
  );
}

/* ─── Main ─── */
export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");

  const ActivePanel = {
    profile: ProfileSettings,
    "api-keys": ApiKeysSettings,
    notifications: NotificationSettings,
    pricing: PricingSettings,
  }[tab];

  return (
    <div className="p-6 max-w-[900px]">
      <div className="mb-5">
        <h1 className="text-xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage your account, integrations, and pricing
        </p>
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 p-1 bg-accent/50 rounded-xl mb-6">
        {TABS.map((t) => {
          const Icon = ICON_MAP[t];
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors",
                tab === t
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {TAB_LABELS[t]}
            </button>
          );
        })}
      </div>

      <ActivePanel />
    </div>
  );
}

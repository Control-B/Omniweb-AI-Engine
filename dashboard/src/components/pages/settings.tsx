"use client";

import { useState } from "react";
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
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const TABS = ["profile", "api-keys", "notifications", "billing"] as const;
type Tab = (typeof TABS)[number];

const ICON_MAP: Record<Tab, React.ElementType> = {
  profile: Building2,
  "api-keys": Key,
  notifications: Bell,
  billing: CreditCard,
};

const TAB_LABELS: Record<Tab, string> = {
  profile: "Profile",
  "api-keys": "API Keys",
  notifications: "Notifications",
  billing: "Billing",
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
  const masked = value.slice(0, 8) + "•".repeat(24);
  return (
    <div className="flex items-center gap-2 font-mono text-sm">
      <span className="select-all">{visible ? value : masked}</span>
      <button onClick={() => setVisible(!visible)} className="p-1 rounded hover:bg-accent">
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
  const [biz, setBiz] = useState({
    name: "Bob's Plumbing",
    email: "bob@bobsplumbing.com",
    website: "https://bobsplumbing.com",
    timezone: "America/New_York",
    webhookUrl: "https://crm.bobsplumbing.com/api/leads",
  });

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Business Info</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {(
            [
              ["name", "Business Name"],
              ["email", "Contact Email"],
              ["website", "Website"],
              ["timezone", "Timezone"],
            ] as const
          ).map(([k, label]) => (
            <div key={k} className="space-y-1.5">
              <Label>{label}</Label>
              <Input
                value={biz[k]}
                onChange={(e) => setBiz({ ...biz, [k]: e.target.value })}
              />
            </div>
          ))}
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
                value={biz.webhookUrl}
                onChange={(e) => setBiz({ ...biz, webhookUrl: e.target.value })}
                placeholder="https://your-crm.com/api/leads"
              />
              <Button variant="outline" size="sm" className="shrink-0">
                <Globe className="w-3.5 h-3.5" />
                Test
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              We'll POST lead data here after every qualifying call
            </p>
          </div>
        </CardContent>
      </Card>

      <Button size="sm">Save Changes</Button>
    </div>
  );
}

/* ─── API Keys Tab ─── */
function ApiKeysSettings() {
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>API Credentials</CardTitle>
          <CardDescription>
            Use these credentials to connect your dashboard to the Omniweb Agent Engine
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1.5">
            <Label>Client ID</Label>
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent/50 border">
              <span className="font-mono text-sm select-all">
                client_9f8e7d6c5b4a3210
              </span>
              <CopyButton value="client_9f8e7d6c5b4a3210" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>API Key</Label>
            <div className="p-2.5 rounded-lg bg-accent/50 border">
              <RevealKey value="sk_test_•••••••••••••••••••••••••••" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>SIP Trunk ID</Label>
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent/50 border">
              <span className="font-mono text-sm select-all">
                ST_abc123def456
              </span>
              <CopyButton value="ST_abc123def456" />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/30">
        <CardHeader>
          <CardTitle className="text-destructive">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Regenerate API Key</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Current key will be revoked immediately
              </p>
            </div>
            <Button variant="destructive" size="sm">
              Regenerate
            </Button>
          </div>
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

      <Button size="sm">Save Preferences</Button>
    </div>
  );
}

/* ─── Billing Tab ─── */
function BillingSettings() {
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/20">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-lg font-bold text-foreground">Pro Plan</p>
                <Badge variant="success">Active</Badge>
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                $99/mo · Unlimited calls · Up to 5 numbers
              </p>
            </div>
            <Button variant="outline" size="sm">
              Manage Plan
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usage This Period</CardTitle>
          <CardDescription>May 1 – May 31, 2025</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            ["Total Calls", "247", "Unlimited"],
            ["Phone Numbers", "2", "5 included"],
            ["SMS Sent", "189", "$0.01/msg after 500"],
            ["Minutes Used", "1,847", "Included"],
          ].map(([label, used, limit]) => (
            <div key={label} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
              <p className="text-sm text-muted-foreground">{label}</p>
              <div className="text-right">
                <p className="text-sm font-semibold text-foreground">{used}</p>
                <p className="text-[10px] text-muted-foreground">{limit}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Payment Method</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-7 rounded bg-accent flex items-center justify-center">
                <CreditCard className="w-4 h-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">•••• •••• •••• 4242</p>
                <p className="text-[11px] text-muted-foreground">Visa · Expires 09/27</p>
              </div>
            </div>
            <Button variant="outline" size="sm">Update</Button>
          </div>
        </CardContent>
      </Card>
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
    billing: BillingSettings,
  }[tab];

  return (
    <div className="p-6 max-w-[900px]">
      <div className="mb-5">
        <h1 className="text-xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage your account, integrations, and billing
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

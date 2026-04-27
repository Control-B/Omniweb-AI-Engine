"use client";

import { useState, useCallback } from "react";
import {
  Bot,
  ArrowRight,
  ArrowLeft,
  Copy,
  Check,
  Loader2,
  Save,
  Sparkles,
  Code,
  Rocket,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Label } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { getAgentConfig, updateAgentConfig, getWidgetEmbed } from "@/lib/api";

const STEPS = [
  { id: 1, label: "Create Agent", icon: Bot },
  { id: 2, label: "Get Embed Code", icon: Code },
  { id: 3, label: "Go Live", icon: Rocket },
] as const;

interface OnboardingProps {
  onComplete: () => void;
}

export function OnboardingFlow({ onComplete }: OnboardingProps) {
  const { user } = useAuth();
  const clientId = user?.client_id || "";

  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // Agent form state
  const [agentName, setAgentName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [websiteDomain, setWebsiteDomain] = useState("");
  const [greeting, setGreeting] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [businessType, setBusinessType] = useState("");

  // Widget info (loaded after save)
  const [embedCode, setEmbedCode] = useState("");

  const handleSaveAgent = useCallback(async () => {
    if (!clientId) return;
    if (!websiteDomain.trim()) {
      setError("Please enter your website domain");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await updateAgentConfig(clientId, {
        agent_name: agentName || "Aria",
        business_name: businessName,
        website_domain: websiteDomain,
        agent_greeting:
          greeting ||
          "Thank you for visiting today, I am your AI assistant... how can I assist you?",
        system_prompt: systemPrompt,
        business_type: businessType,
      });

      // Try to load embed code
      try {
        const w = await getWidgetEmbed(clientId);
        setEmbedCode(w.embed_code || "");
      } catch {
        // Marketing site (omniweb.ai) is a different app — widget lives on the dashboard/engine host.
        const origin = (
          process.env.NEXT_PUBLIC_PLATFORM_URL ||
          (typeof window !== "undefined" ? window.location.origin : "")
        ).replace(/\/$/, "");
        setEmbedCode(
          `<!-- Omniweb AI Widget — iframe loads Deepgram voice UI from your engine dashboard -->
<iframe
  src="${origin}/widget/${clientId}"
  title="Omniweb AI"
  allow="microphone; autoplay"
  style="position:fixed;bottom:0;right:0;width:420px;height:640px;border:0;z-index:99999"
></iframe>`
        );
      }

      setStep(2);
    } catch (err: any) {
      setError(err.message || "Failed to save agent configuration");
    } finally {
      setSaving(false);
    }
  }, [clientId, agentName, businessName, websiteDomain, greeting, systemPrompt, businessType]);

  const copyEmbed = () => {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const finishOnboarding = () => {
    localStorage.setItem("omniweb_setup_complete", "1");
    onComplete();
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background">
      <div className="w-full max-w-[640px] space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary/10 mb-2">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">
            Set up your AI Agent
          </h1>
          <p className="text-sm text-muted-foreground">
            Get your voice AI live on your website in under 2 minutes
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-2">
              <div
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                  step >= s.id
                    ? "bg-primary/10 text-primary"
                    : "bg-secondary text-muted-foreground"
                )}
              >
                <s.icon className="w-3.5 h-3.5" />
                {s.label}
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={cn(
                    "w-8 h-px",
                    step > s.id ? "bg-primary" : "bg-border"
                  )}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step 1: Create Agent */}
        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="w-5 h-5" />
                Tell us about your business
              </CardTitle>
              <CardDescription>
                We'll use this to create a personalized AI agent for your
                website. You can fine-tune everything later.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label>Agent Name</Label>
                  <Input
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    placeholder="e.g. Aria, Alex, Sam"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Your AI&apos;s name — visitors will see this
                  </p>
                </div>
              <div className="space-y-1.5">
                <Label>Business Name</Label>
                <Input
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  placeholder="e.g. Bob's Plumbing"
                />
              </div>
            </div>

              <div className="space-y-1.5">
                <Label>Website Domain <span className="text-destructive">*</span></Label>
                <Input
                  value={websiteDomain}
                  onChange={(e) => setWebsiteDomain(e.target.value)}
                  placeholder="e.g. bobsplumbing.com"
                />
                <p className="text-[11px] text-muted-foreground">
                  Your company&apos;s website — each domain gets its own AI agent
                </p>
              </div>              <div className="space-y-1.5">
                <Label>Business Type</Label>
                <Input
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  placeholder="e.g. plumbing, dental practice, law firm, e-commerce"
                />
              </div>

              <div className="space-y-1.5">
                <Label>Greeting Message</Label>
                <Textarea
                  value={greeting}
                  onChange={(e) => setGreeting(e.target.value)}
                  placeholder="Thank you for visiting today, I am your AI assistant... how can I assist you?"
                  rows={2}
                />
                <p className="text-[11px] text-muted-foreground">
                  The first thing your agent says — leave blank for a smart default
                </p>
              </div>

              <div className="space-y-1.5">
                <Label>
                  Instructions{" "}
                  <span className="text-muted-foreground font-normal">
                    (optional)
                  </span>
                </Label>
                <Textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="Tell the agent what it should know about your business, services, hours, policies, etc. We'll generate a great default if you leave this blank."
                  rows={5}
                  className="font-mono text-xs"
                />
              </div>

              {error && (
                <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">
                  {error}
                </div>
              )}

              <div className="flex justify-end pt-2">
                <Button onClick={handleSaveAgent} disabled={saving}>
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  {saving ? "Creating Agent..." : "Create Agent"}
                  {!saving && <ArrowRight className="w-4 h-4 ml-1" />}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Embed Code */}
        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code className="w-5 h-5" />
                Add the widget to your website
              </CardTitle>
              <CardDescription>
                Copy this snippet and paste it into your website&apos;s HTML,
                just before the closing{" "}
                <code className="text-xs bg-secondary px-1 py-0.5 rounded">
                  &lt;/body&gt;
                </code>{" "}
                tag.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <pre className="bg-secondary p-4 rounded-lg text-xs overflow-x-auto font-mono whitespace-pre-wrap leading-relaxed">
                  {embedCode}
                </pre>
                <Button
                  size="sm"
                  variant="outline"
                  className="absolute top-2 right-2"
                  onClick={copyEmbed}
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-green-500" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                  {copied ? "Copied!" : "Copy"}
                </Button>
              </div>

              <div className="bg-primary/5 border border-primary/20 rounded-lg p-4 space-y-2">
                <p className="text-sm font-medium text-foreground">
                  Where to paste it
                </p>
                <div className="font-mono text-xs text-muted-foreground bg-secondary rounded-md p-3 leading-relaxed">
                  <span className="text-muted-foreground/60">
                    &lt;html&gt;
                    <br />
                    &nbsp;&nbsp;&lt;body&gt;
                    <br />
                    &nbsp;&nbsp;&nbsp;&nbsp;...your website content...
                    <br />
                    <br />
                  </span>
                  <span className="text-primary font-semibold">
                    &nbsp;&nbsp;&nbsp;&nbsp;{`<!-- Paste the snippet here -->`}
                  </span>
                  <br />
                  <span className="text-muted-foreground/60">
                    &nbsp;&nbsp;&lt;/body&gt;
                    <br />
                    &lt;/html&gt;
                  </span>
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                Works with any website — WordPress, Shopify, Squarespace, Wix,
                custom HTML, React, Next.js, and more. The widget appears as a
                floating button in the bottom-right corner.
              </p>

              <div className="flex justify-between pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setStep(1)}
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back
                </Button>
                <Button onClick={() => setStep(3)}>
                  I&apos;ve added it
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Done */}
        {step === 3 && (
          <Card>
            <CardContent className="p-10 text-center space-y-4">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 mb-2">
                <Rocket className="w-8 h-8 text-emerald-400" />
              </div>
              <h2 className="text-xl font-bold text-foreground">
                You&apos;re all set! 🎉
              </h2>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Your AI agent is live and ready to talk to your website
                visitors. Head to the dashboard to see calls, leads, and fine-tune
                your agent.
              </p>

              <div className="flex flex-col items-center gap-2 pt-4">
                <Button size="lg" onClick={finishOnboarding}>
                  <Sparkles className="w-4 h-4" />
                  Go to Dashboard
                </Button>
                <button
                  onClick={() => setStep(2)}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  ← Back to embed code
                </button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Skip link */}
        {step === 1 && (
          <div className="text-center">
            <button
              onClick={finishOnboarding}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Skip setup — I&apos;ll do this later
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import { Check, Copy, ExternalLink, Globe, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Textarea } from "@/components/ui/input";

function extractScriptAttributes(snippet: string) {
  const scriptMatch = snippet.match(/<script\b([^>]*)><\/script>/i) || snippet.match(/<script\b([^>]*)\/>/i);
  if (!scriptMatch) {
    throw new Error("Paste the full Omniweb script tag.");
  }

  const attrs = scriptMatch[1];
  const srcMatch = attrs.match(/src=["']([^"']+)["']/i);
  if (!srcMatch) {
    throw new Error("The script tag must include a src attribute.");
  }

  const dataAttributes = Array.from(attrs.matchAll(/(data-[\w-]+)=["']([^"']+)["']/gi)).reduce<Record<string, string>>(
    (acc, [, key, value]) => {
      acc[key] = value;
      return acc;
    },
    {}
  );

  return {
    src: srcMatch[1],
    dataAttributes,
  };
}

export default function WidgetDemoPage() {
  const [snippet, setSnippet] = useState(`<!-- Omniweb AI Widget -->\n<script\n  src="https://omniweb.ai/widget/loader.js"\n  data-embed-code="PASTE_YOUR_EMBED_CODE_HERE"\n  data-agent-id="PASTE_YOUR_CLIENT_ID_HERE"\n  data-engine-url="https://omniweb-engine-rs6fr.ondigitalocean.app"\n  async\n></script>`);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [injecting, setInjecting] = useState(false);

  const pageSourceHint = useMemo(
    () => `    ...page content...\n\n    <!-- Paste the Omniweb snippet here -->\n  </body>`,
    []
  );

  async function copyHint() {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function injectWidget() {
    setError("");
    setMessage("");
    setInjecting(true);
    try {
      const parsed = extractScriptAttributes(snippet);
      const existing = document.getElementById("omniweb-demo-loader");
      if (existing) {
        existing.remove();
      }

      const script = document.createElement("script");
      script.id = "omniweb-demo-loader";
      script.src = parsed.src;
      script.async = true;
      Object.entries(parsed.dataAttributes).forEach(([key, value]) => {
        script.setAttribute(key, value);
      });

      document.body.appendChild(script);
      setMessage("Widget script injected. The floating widget should appear in the bottom-right corner.");
    } catch (err: any) {
      setError(err.message || "Failed to inject widget snippet.");
    } finally {
      setInjecting(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <section className="border-b border-border bg-gradient-to-b from-primary/10 via-background to-background">
        <div className="mx-auto max-w-6xl px-6 py-16 lg:flex lg:items-center lg:justify-between lg:gap-12">
          <div className="max-w-2xl space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Demo customer website
            </div>
            <div className="space-y-4">
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
                See how Omniweb looks on a real customer landing page
              </h1>
              <p className="text-base text-muted-foreground sm:text-lg">
                Copy your widget snippet from the dashboard, paste it here, and test the exact script your customers would install before the closing <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">&lt;/body&gt;</code> tag.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span className="rounded-full border border-border px-3 py-1">Plumber demo brand</span>
              <span className="rounded-full border border-border px-3 py-1">Paste-and-test widget flow</span>
              <span className="rounded-full border border-border px-3 py-1">No extra repo needed</span>
            </div>
          </div>

          <Card className="mt-10 w-full max-w-xl lg:mt-0">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Globe className="h-4 w-4" />
                Install snippet
              </CardTitle>
              <CardDescription>
                Paste the script generated in Agent Config → Widget & Embed, then inject it into this page.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="widget-snippet">Omniweb embed snippet</Label>
                <Textarea
                  id="widget-snippet"
                  value={snippet}
                  onChange={(e) => setSnippet(e.target.value)}
                  className="min-h-[220px] font-mono text-xs"
                />
              </div>
              <div className="rounded-lg border border-border bg-secondary/40 p-3 font-mono text-xs text-muted-foreground whitespace-pre-wrap">
                {pageSourceHint}
              </div>
              {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}
              {message && (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
                  {message}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button onClick={injectWidget} disabled={injecting}>
                  {injecting && <Loader2 className="h-4 w-4 animate-spin" />}
                  Inject Widget
                </Button>
                <Button variant="outline" onClick={copyHint}>
                  {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                  {copied ? "Copied" : "Copy Snippet"}
                </Button>
                <Button variant="outline" onClick={() => window.location.assign("/login")}>
                  <ExternalLink className="h-4 w-4" />
                  Back to Admin
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <main className="mx-auto max-w-6xl px-6 py-14 space-y-12">
        <section className="grid gap-6 md:grid-cols-3">
          {[
            ["24/7 Dispatch", "Capture calls and web visitors even after hours without losing booked jobs."],
            ["Instant Answers", "Let customers ask about pricing, coverage areas, and emergency availability in real time."],
            ["Qualified Leads", "Collect contact info and route hot prospects straight to your sales or service team."],
          ].map(([title, description]) => (
            <Card key={title}>
              <CardHeader>
                <CardTitle>{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </section>

        <section className="grid gap-8 lg:grid-cols-[1.1fr,0.9fr]">
          <Card>
            <CardHeader>
              <CardTitle>Why this page helps</CardTitle>
              <CardDescription>
                It mirrors the customer journey: grab the snippet, paste it near <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">&lt;/body&gt;</code>, and verify the widget launches.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>Use this route when testing new widget loader changes, onboarding instructions, or client-specific embed snippets.</p>
              <p>If the widget does not appear, confirm the snippet still contains the correct <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">data-embed-code</code>, <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">data-agent-id</code>, and engine URL values.</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recommended test flow</CardTitle>
              <CardDescription>Quick loop for owner onboarding and widget validation.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>1. Create the owner account at <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">/admin/setup</code>.</p>
              <p>2. Open Agent Config and copy the snippet from <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">Widget &amp; Embed</code>.</p>
              <p>3. Paste it into this page and click <span className="font-medium text-foreground">Inject Widget</span>.</p>
              <p>4. Invite teammates from <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">Admin → Team</code> and share the generated invite link if needed.</p>
            </CardContent>
          </Card>
        </section>
      </main>
    </div>
  );
}
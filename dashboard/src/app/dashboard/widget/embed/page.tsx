"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getWidgetEmbedCode, patchSetupProgress } from "@/lib/api";

export default function WidgetEmbedPage() {
  const [loading, setLoading] = useState(true);
  const [snippet, setSnippet] = useState("");
  const [copied, setCopied] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await getWidgetEmbedCode();
        if (!cancelled) setSnippet(r.embed_snippet);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function copy() {
    if (!snippet) return;
    void navigator.clipboard.writeText(snippet);
    setCopied(true);
    setToast("Copied to clipboard");
    window.setTimeout(() => {
      setCopied(false);
      setToast("");
    }, 2500);
  }

  async function markInstalled() {
    try {
      await patchSetupProgress({ embed_installed: true });
      setToast("Nice — we marked embed code as installed.");
      window.setTimeout(() => setToast(""), 3000);
    } catch {
      setToast("Could not update progress");
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
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Install your widget</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Install your widget and start capturing leads from your site.
        </p>
      </div>

      {toast && (
        <div className="text-sm rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 px-3 py-2">
          {toast}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Embed snippet</CardTitle>
          <CardDescription>
            Paste this code before the closing <code className="text-xs bg-secondary px-1 rounded">&lt;/body&gt;</code> tag on
            your website.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <pre className="bg-secondary p-4 rounded-lg text-xs overflow-x-auto font-mono whitespace-pre-wrap">
              {snippet}
            </pre>
            <Button type="button" size="sm" variant="outline" className="absolute top-2 right-2" onClick={copy}>
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>

          <div className="space-y-2 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Platform tips</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <strong className="text-foreground">Shopify:</strong> Online Store → Themes → Edit code →{" "}
                <code className="text-xs">theme.liquid</code> → paste before <code className="text-xs">&lt;/body&gt;</code>
              </li>
              <li>
                <strong className="text-foreground">WordPress:</strong> Appearance → Theme File Editor or a header/footer
                script plugin
              </li>
              <li>
                <strong className="text-foreground">Webflow:</strong> Site settings → Custom code → Footer code
              </li>
              <li>
                <strong className="text-foreground">Framer:</strong> Site settings → Custom code → End of body
              </li>
              <li>
                <strong className="text-foreground">Custom HTML:</strong> Paste before <code className="text-xs">&lt;/body&gt;</code>
              </li>
            </ul>
          </div>

          <Button type="button" variant="secondary" onClick={() => void markInstalled()}>
            I&apos;ve installed the embed code
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

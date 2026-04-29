"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getMeWorkspace, postWidgetTest } from "@/lib/api";

function getEngineOrigin(): string {
  const configured =
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_ENGINE_URL?.trim() ||
    "";
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window !== "undefined") return window.location.origin.replace(/\/$/, "");
  return "http://localhost:8000";
}

export default function WidgetTestPage() {
  const [loading, setLoading] = useState(true);
  const [key, setKey] = useState<string | null>(null);
  const engineOrigin = useMemo(() => getEngineOrigin(), []);

  const iframeSrcDoc = useMemo(() => {
    if (!key) return "";
    const esc = engineOrigin.replace(/"/g, "&quot;");
    const k = key.replace(/"/g, "&quot;");
    return `<!DOCTYPE html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head><body style="margin:0;min-height:100vh;background:#1a1a1f;">
<script src="${esc}/widget.js" data-widget-key="${k}" data-api-base="${esc}" async><\/script>
</body></html>`;
  }, [key, engineOrigin]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ws = await getMeWorkspace();
        if (!cancelled) setKey(ws.widget.public_widget_key);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    void postWidgetTest().catch(() => {});
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!key) {
    return (
      <div className="p-6 max-w-lg">
        <p className="text-sm text-muted-foreground">Complete onboarding to get a widget key.</p>
        <Button asChild className="mt-4">
          <Link href="/onboarding">Onboarding</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Test widget</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Test your agent before installing it on your website.
        </p>
      </div>

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
        This is a private preview. Your widget is not live until you install the embed code on your site.
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Live preview</CardTitle>
          <CardDescription>
            The same script your visitors will load — chat runs against the production API with your widget key.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="relative rounded-lg border border-border overflow-hidden bg-[#1a1a1f] h-[min(70vh,560px)]">
            <iframe title="Omniweb widget preview" className="w-full h-full border-0" srcDoc={iframeSrcDoc} />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="secondary" onClick={() => void postWidgetTest()}>
          Record test again
        </Button>
        <Button asChild>
          <Link href="/dashboard/widget/embed">Get embed code</Link>
        </Button>
      </div>
    </div>
  );
}

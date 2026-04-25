"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

const STORAGE_KEY = "omniweb_widget_demo_client_id";

function engineBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_ENGINE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

interface WidgetTesterProps {
  title?: string;
  description?: string;
  showChecklist?: boolean;
  className?: string;
  previewClassName?: string;
}

export function WidgetTester({
  title = "Try the AI widget",
  description = "Load your embeddable assistant in an iframe and talk to it in real time.",
  showChecklist = false,
  className = "rounded-2xl border border-white/10 bg-slate-900/40 p-6",
  previewClassName = "w-full min-h-[min(85vh,720px)] bg-transparent",
}: WidgetTesterProps) {
  const [clientId, setClientId] = useState("");
  const [showFrame, setShowFrame] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("client")?.trim();
    if (q) {
      setClientId(q);
      return;
    }
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setClientId(saved);
    } catch {
      /* ignore */
    }
  }, []);

  const iframeSrc = useMemo(() => {
    const id = clientId.trim();
    if (!id) return "";
    return `/widget/${encodeURIComponent(id)}`;
  }, [clientId]);

  const loadWidget = useCallback(() => {
    const id = clientId.trim();
    if (!id) return;
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore */
    }
    setShowFrame(true);
  }, [clientId]);

  const copySnippet = useCallback(() => {
    const id = clientId.trim();
    if (!id) return;
    const origin =
      typeof window !== "undefined" ? window.location.origin.replace(/\/$/, "") : "";
    const snippet = `<!-- Omniweb widget preview — replace YOUR_CLIENT_UUID -->
<iframe
  src="${origin}/widget/${id}"
  title="Omniweb AI"
  allow="microphone"
  style="position:fixed;bottom:0;right:0;width:420px;height:640px;border:0;z-index:99999"
></iframe>`;
    void (async () => {
      try {
        await navigator.clipboard.writeText(snippet);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        setCopied(false);
      }
    })();
  }, [clientId]);

  return (
    <div className={className}>
      <div className="mb-6">
        <h2 className="text-xl font-semibold tracking-tight text-white">{title}</h2>
        <p className="mt-2 text-sm text-slate-400 leading-relaxed">{description}</p>
      </div>

      {showChecklist && (
        <section className="rounded-2xl border border-white/10 bg-slate-950/40 p-6 mb-6">
          <h3 className="text-sm font-semibold text-white mb-4">Checklist</h3>
          <ol className="list-decimal list-inside space-y-2 text-sm text-slate-300 leading-relaxed">
            <li>
              Start the engine:{" "}
              <code className="rounded bg-black/40 px-1.5 py-0.5 text-cyan-200">
                uvicorn app.main:app --reload --port 8000
              </code>
              .
            </li>
            <li>
              Set <code className="rounded bg-black/40 px-1.5 py-0.5">LIVEKIT_URL</code>, <code className="rounded bg-black/40 px-1.5 py-0.5">LIVEKIT_API_KEY</code>, and <code className="rounded bg-black/40 px-1.5 py-0.5">LIVEKIT_API_SECRET</code> in the engine <code className="rounded bg-black/40 px-1.5 py-0.5">.env</code>.
            </li>
            <li>
              Point the dashboard at the engine with <code className="rounded bg-black/40 px-1.5 py-0.5">NEXT_PUBLIC_ENGINE_URL</code>.
            </li>
            <li>
              Use a <code className="rounded bg-black/40 px-1.5 py-0.5">client_id</code> from <code className="rounded bg-black/40 px-1.5 py-0.5">agent_config</code>.
            </li>
          </ol>
          <p className="mt-4 text-xs text-slate-500">
            Engine this build talks to:{" "}
            <span className="text-slate-400 font-mono break-all">{engineBaseUrl()}</span>
          </p>
        </section>
      )}

      <section className="rounded-2xl border border-white/10 bg-slate-950/40 p-6 mb-6">
        <label htmlFor="widget-tester-client-id" className="block text-sm font-medium text-slate-200 mb-2">
          Client ID (UUID)
        </label>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            id="widget-tester-client-id"
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            className="flex-1 rounded-xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
          />
          <button
            type="button"
            onClick={loadWidget}
            disabled={!clientId.trim()}
            className="rounded-xl bg-cyan-600 px-6 py-3 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-40 disabled:pointer-events-none transition-colors"
          >
            Load widget
          </button>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Tip: use the same agent/client UUID you use in admin and widget links.
        </p>
      </section>

      <div className="flex flex-wrap gap-3 mb-6">
        <button
          type="button"
          onClick={copySnippet}
          disabled={!clientId.trim()}
          className="text-sm text-cyan-400 hover:text-cyan-300 disabled:opacity-40 underline-offset-2 hover:underline"
        >
          {copied ? "Copied iframe snippet" : "Copy iframe embed snippet"}
        </button>
        <span className="text-slate-600">·</span>
        {iframeSrc ? (
          <Link href={iframeSrc} className="text-sm text-slate-400 hover:text-white">
            Open widget full page →
          </Link>
        ) : (
          <span className="text-sm text-slate-600">Open widget full page →</span>
        )}
      </div>

      {showFrame && iframeSrc ? (
        <div className="rounded-2xl border border-cyan-500/20 overflow-hidden bg-black/40 shadow-2xl shadow-cyan-950/30">
          <p className="text-xs text-slate-500 px-4 py-2 border-b border-white/5 bg-slate-900/60">
            Preview — allow microphone when the browser asks.
          </p>
          <iframe
            title="Omniweb AI widget"
            src={iframeSrc}
            allow="microphone"
            className={previewClassName}
          />
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-white/10 py-20 text-center text-sm text-slate-500">
          Enter a client ID and click "Load widget" to preview here.
        </div>
      )}
    </div>
  );
}
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowUp,
  ChevronDown,
  MessageCircle,
  Mic,
  X,
} from "lucide-react";
import {
  DeepgramVoiceAgentSession,
  type TranscriptLine,
} from "@/lib/deepgramVoiceAgentClient";

/**
 * Omniweb embeddable widget — Deepgram Voice Agent (orb + panel).
 *
 * URL: ``/widget/{clientId}`` — ``clientId`` is the Omniweb ``client_id`` (UUID).
 * Query: ``?panel=1`` opens the chat panel on load (easier widget-only testing).
 */

type LangOption = { code: string; label: string; retell: string; flag?: string };
type UiMode = "voice" | "text";

function engineBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_ENGINE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

const LANG_FLAGS: Record<string, string> = {
  en: "🇺🇸", es: "🇪🇸", fr: "🇫🇷", de: "🇩🇪", it: "🇮🇹",
  pt: "🇧🇷", ja: "🇯🇵", ko: "🇰🇷", zh: "🇨🇳", hi: "🇮🇳", multi: "🌐",
};

function flagEmoji(lang: LangOption): string {
  return lang.flag || LANG_FLAGS[lang.code] || "🌐";
}

type BootstrapPayload = {
  websocket_url: string;
  access_token: string;
  settings: Record<string, unknown>;
};

function normalizeAgentId(raw: string | string[] | undefined): string | undefined {
  if (raw === undefined) return undefined;
  const v = Array.isArray(raw) ? raw[0] : raw;
  const s = typeof v === "string" ? v.trim() : "";
  return s || undefined;
}

export default function VoiceWidgetPage() {
  const params = useParams<{ agentId: string }>();
  const agentId = normalizeAgentId(params?.agentId);
  const [panelOpen, setPanelOpen] = useState(false);
  const [langs, setLangs] = useState<LangOption[]>([]);
  const [langOpen, setLangOpen] = useState(false);
  const [selectedLang, setSelectedLang] = useState<LangOption | null>(null);
  const [mode, setMode] = useState<UiMode>("voice");
  const [sessionOn, setSessionOn] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [textDraft, setTextDraft] = useState("");
  const sessionRef = useRef<DeepgramVoiceAgentSession | null>(null);

  useEffect(() => {
    try {
      const q = new URLSearchParams(window.location.search);
      if (q.get("panel") === "1" || q.get("open") === "1") {
        setPanelOpen(true);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${engineBaseUrl()}/api/chat/languages`);
        if (!res.ok) return;
        const data = (await res.json()) as { languages?: LangOption[] };
        const list = data.languages || [];
        if (cancelled) return;
        setLangs(list);
        const def = list.find((l) => l.code === "en") || list[0] || null;
        setSelectedLang(def);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const subtitle = useMemo(() => {
    if (connecting) return "Connecting…";
    if (sessionOn) return mode === "voice" ? "Listening…" : "Type a message";
    return "Ready to talk";
  }, [connecting, sessionOn, mode]);

  const stopSession = useCallback(async () => {
    await sessionRef.current?.disconnect();
    sessionRef.current = null;
    setSessionOn(false);
    setConnecting(false);
  }, []);

  useEffect(() => {
    return () => {
      void stopSession();
    };
  }, [stopSession]);

  const bootstrap = useCallback(async (): Promise<BootstrapPayload> => {
    if (!agentId) throw new Error("Missing agent id");
    const res = await fetch(`${engineBaseUrl()}/api/deepgram/voice-agent/bootstrap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: agentId,
        language: selectedLang?.code || "en",
      }),
    });
    if (!res.ok) {
      const raw = await res.text();
      let msg = raw || `HTTP ${res.status}`;
      try {
        const j = JSON.parse(raw) as { detail?: unknown };
        if (j.detail != null) {
          msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
        }
      } catch {
        /* keep text */
      }
      throw new Error(msg);
    }
    return (await res.json()) as BootstrapPayload;
  }, [agentId, selectedLang?.code]);

  const startSession = useCallback(
    async (withMic: boolean) => {
      if (!agentId) return;
      setConnecting(true);
      setErrorMsg("");
      try {
        await stopSession();
        const payload = await bootstrap();
        const session = new DeepgramVoiceAgentSession({
          onTranscript: (line) => {
            setLines((prev) => [...prev, line]);
          },
          onError: (m) => setErrorMsg(m),
          onClose: () => {
            setSessionOn(false);
          },
        });
        sessionRef.current = session;
        await session.connect({
          websocketUrl: payload.websocket_url,
          accessToken: payload.access_token,
          settings: payload.settings,
          enableMic: withMic,
        });
        setSessionOn(true);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to connect";
        setErrorMsg(msg);
        await stopSession();
      } finally {
        setConnecting(false);
      }
    },
    [agentId, bootstrap, stopSession],
  );

  const onVoiceClick = useCallback(async () => {
    setMode("voice");
    setPanelOpen(true);
    await startSession(true);
  }, [startSession]);

  const onTextMode = useCallback(async () => {
    setMode("text");
    setPanelOpen(true);
    if (!sessionOn) {
      await startSession(false);
      return;
    }
    if (mode === "voice") {
      await startSession(false);
    }
  }, [sessionOn, mode, startSession]);

  const sendText = useCallback(async () => {
    const t = textDraft.trim();
    if (!t) return;
    setMode("text");
    if (!sessionRef.current) {
      await startSession(false);
    }
    sessionRef.current?.injectUserMessage(t);
    setTextDraft("");
  }, [textDraft, startSession]);

  if (!agentId) {
    return (
      <div className="min-h-dvh flex items-center justify-center bg-slate-950 px-4 text-center text-slate-300 text-sm">
        <p>
          Invalid widget URL — missing client id. Use{" "}
          <code className="text-cyan-400">/widget/&lt;your-uuid&gt;</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-dvh w-full bg-slate-950 relative">
      <div className="fixed inset-0 z-[9999] pointer-events-none font-sans">
      {/* Floating orb — overflow clips glow so it reads as one control (no “double” halo). */}
      <button
        type="button"
        onClick={() => setPanelOpen((o) => !o)}
        className="pointer-events-auto absolute bottom-6 right-6 h-16 w-16 rounded-full relative overflow-hidden shadow-[0_8px_28px_rgba(56,189,248,0.4)] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 focus-visible:ring-offset-0 transition-transform hover:scale-105 active:scale-95"
        style={{
          background:
            "conic-gradient(from 200deg at 50% 50%, #0ea5e9 0deg, #e0f2fe 80deg, #0369a1 200deg, #7dd3fc 320deg, #0ea5e9 360deg)",
          boxShadow:
            "inset 0 2px 10px rgba(255,255,255,0.32), 0 0 0 1px rgba(255,255,255,0.1)",
        }}
        aria-label={panelOpen ? "Close assistant" : "Open Omniweb AI"}
      >
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-full bg-gradient-to-br from-white/20 to-transparent opacity-75"
        />
      </button>

      {/* Panel */}
      {panelOpen && (
        <div className="pointer-events-auto absolute bottom-24 right-6 w-[min(100vw-2rem,22rem)] max-h-[min(85vh,32rem)] flex flex-col rounded-2xl border border-white/10 bg-[#0b1220] shadow-2xl text-slate-100 overflow-hidden">
          <header className="flex items-start gap-3 px-4 pt-4 pb-3 border-b border-white/5">
            <div
              className="h-10 w-10 shrink-0 rounded-full"
              style={{
                background:
                  "conic-gradient(from 210deg at 50% 50%, #38bdf8, #f8fafc, #0284c7, #38bdf8)",
                boxShadow: "inset 0 1px 6px rgba(255,255,255,0.4)",
              }}
            />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm tracking-tight">Omniweb AI</p>
              <p className="text-xs text-slate-400 truncate">{subtitle}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setPanelOpen(false);
                void stopSession();
              }}
              className="rounded-lg p-1.5 text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </header>

          {errorMsg ? (
            <div className="mx-3 mt-3 rounded-lg bg-red-950/80 border border-red-500/30 px-3 py-2 text-xs text-red-200 flex flex-wrap items-center gap-2">
              <span className="flex-1 min-w-0 break-words">{errorMsg}</span>
              <button
                type="button"
                className="shrink-0 text-red-300 underline hover:text-red-100"
                onClick={() => {
                  setErrorMsg("");
                  void (mode === "voice" ? onVoiceClick() : onTextMode());
                }}
              >
                Retry
              </button>
            </div>
          ) : null}

          <div className="flex-1 min-h-[10rem] max-h-[14rem] overflow-y-auto px-4 py-3 space-y-2 text-sm">
            {lines.length === 0 && !errorMsg && (
              <p className="text-slate-500 text-xs leading-relaxed">
                Start voice or type below. Your conversation appears here in real time.
              </p>
            )}
            {lines.map((ln, i) => (
              <div
                key={`${i}-${ln.role}`}
                className={`rounded-lg px-3 py-2 ${
                  ln.role === "user"
                    ? "bg-slate-800/80 ml-4 text-slate-100"
                    : "bg-cyan-950/40 mr-4 text-cyan-50 border border-cyan-500/15"
                }`}
              >
                <p className="text-[10px] uppercase tracking-wide opacity-60 mb-0.5">
                  {ln.role === "user" ? "You" : "Assistant"}
                </p>
                <p className="whitespace-pre-wrap break-words">{ln.content}</p>
              </div>
            ))}
          </div>

          <div className="px-4 pb-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Language</p>
            <div className="relative">
              <button
                type="button"
                onClick={() => setLangOpen((o) => !o)}
                disabled={sessionOn}
                className="w-full flex items-center justify-between gap-2 rounded-xl bg-slate-900/80 border border-white/10 px-3 py-2 text-sm text-left hover:bg-slate-900 disabled:opacity-50"
              >
                <span className="flex items-center gap-2 truncate">
                  <span className="text-lg">{selectedLang ? flagEmoji(selectedLang) : "🌐"}</span>
                  <span className="truncate">{selectedLang?.label || "English"}</span>
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
              </button>
              {langOpen && langs.length > 0 && (
                <ul className="absolute z-10 bottom-full mb-1 w-full max-h-48 overflow-auto rounded-xl border border-white/10 bg-[#0f172a] shadow-xl py-1 text-sm">
                  {langs.map((l) => (
                    <li key={l.code}>
                      <button
                        type="button"
                        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-white/5 text-left"
                        onClick={() => {
                          setSelectedLang(l);
                          setLangOpen(false);
                        }}
                      >
                        <span>{flagEmoji(l)}</span>
                        <span className="truncate">{l.label}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="flex gap-2 px-4 pb-3">
            <button
              type="button"
              onClick={() => void onVoiceClick()}
              disabled={connecting}
              className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium transition-all ${
                mode === "voice" && sessionOn
                  ? "bg-cyan-500 text-slate-950 shadow-[0_0_24px_rgba(34,211,238,0.35)]"
                  : "bg-cyan-600/90 text-white hover:bg-cyan-500"
              } disabled:opacity-60`}
            >
              <Mic className="h-4 w-4" />
              Voice
            </button>
            <button
              type="button"
              onClick={() => void onTextMode()}
              disabled={connecting}
              className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium border border-white/10 transition-all ${
                mode === "text"
                  ? "bg-slate-800 text-white"
                  : "bg-slate-900/60 text-slate-300 hover:bg-slate-800"
              } disabled:opacity-60`}
            >
              <MessageCircle className="h-4 w-4" />
              Text
            </button>
          </div>

          <div className="flex items-end gap-2 px-4 pb-4 border-t border-white/5 pt-3">
            <textarea
              rows={2}
              value={textDraft}
              onChange={(e) => setTextDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendText();
                }
              }}
              placeholder="Start voice or type a message…"
              className="flex-1 resize-none rounded-xl bg-slate-900/80 border border-white/10 px-3 py-2 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
            />
            <button
              type="button"
              onClick={() => void sendText()}
              disabled={connecting || !textDraft.trim()}
              className="shrink-0 h-11 w-11 rounded-full bg-violet-600 hover:bg-violet-500 disabled:opacity-40 flex items-center justify-center text-white"
              aria-label="Send"
            >
              <ArrowUp className="h-5 w-5" />
            </button>
          </div>

          {sessionOn && mode === "voice" && (
            <div className="px-4 pb-3 flex justify-center">
              <button
                type="button"
                onClick={() => void stopSession()}
                className="text-xs text-slate-400 hover:text-slate-200 underline"
              >
                End voice session
              </button>
            </div>
          )}
        </div>
      )}
      </div>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
 * - With `agentId`: ``/widget/{clientId}`` — tenant UUID.
 * - Without `agentId`: ``/widget`` — engine uses ``LANDING_PAGE_CLIENT_ID`` (set in API env).
 * Query: ``?panel=1`` opens the chat panel on load.
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

/** Baked at build time — same UUID as API ``LANDING_PAGE_CLIENT_ID`` for anonymous ``/widget``. */
function publicLandingClientId(): string | undefined {
  const v = process.env.NEXT_PUBLIC_LANDING_PAGE_CLIENT_ID?.trim();
  return v || undefined;
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

export function VoiceWidgetClient({ agentId }: { agentId?: string }) {
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
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  // Read ?voice= and ?mode= from the URL (set by the test console iframe src).
  const [voiceOverride, setVoiceOverride] = useState<string | null>(null);

  const useLanding = !agentId?.trim();

  useEffect(() => {
    try {
      const q = new URLSearchParams(window.location.search);
      if (q.get("panel") === "1" || q.get("open") === "1") {
        setPanelOpen(true);
      }
      const v = q.get("voice");
      if (v) setVoiceOverride(v.trim());
      const m = q.get("mode") as UiMode | null;
      if (m === "text" || m === "voice") setMode(m);
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

  useEffect(() => {
    const node = transcriptRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [lines.length, errorMsg]);

  const bootstrap = useCallback(async (): Promise<BootstrapPayload> => {
    const body: { client_id?: string; widget_key?: string; language: string; voice_override?: string } = {
      language: selectedLang?.code || "en",
    };
    if (voiceOverride) body.voice_override = voiceOverride;
    const landingClientId = publicLandingClientId();
    if (agentId?.trim()) {
      body.client_id = agentId.trim();
    } else if (landingClientId) {
      body.widget_key = landingClientId;
    }
    const res = await fetch(`${engineBaseUrl()}/api/chat/voice-agent/bootstrap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const raw = await res.text();
      let msg = raw || `HTTP ${res.status}`;
      const ctype = res.headers.get("content-type") || "";
      const looksHtml =
        ctype.includes("html") ||
        raw.trimStart().toLowerCase().startsWith("<!doctype") ||
        raw.includes("App Platform failed to forward");
      try {
        const j = JSON.parse(raw) as { detail?: unknown };
        if (j.detail != null) {
          msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
        }
      } catch {
        if (looksHtml) {
          msg = `Engine unreachable or timed out (HTTP ${res.status}). Check /health and API logs.`;
        }
      }
      throw new Error(msg);
    }
    return (await res.json()) as BootstrapPayload;
  }, [agentId, selectedLang?.code, voiceOverride]);

  const startSession = useCallback(
    async (withMic: boolean) => {
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
    [bootstrap, stopSession],
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

  return (
    <div className="min-h-dvh w-full bg-slate-950 [font-size:14px] [-webkit-text-size-adjust:100%] [text-size-adjust:100%]">
      {useLanding ? (
        <p className="fixed top-0 left-0 right-0 z-[10000] text-center text-[10px] text-slate-500 py-1.5 px-2 border-b border-white/5 bg-slate-900/80">
          Demo: using engine <code className="text-cyan-600/80">LANDING_PAGE_CLIENT_ID</code> (no
          path UUID). Set that env on the API to a real client with an agent config.
        </p>
      ) : null}
      <button
        type="button"
        onClick={() => setPanelOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-[9999] h-16 w-16 rounded-full overflow-hidden shadow-[0_8px_28px_rgba(56,189,248,0.4)] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 focus-visible:ring-offset-0 transition-transform hover:scale-105 active:scale-95"
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

      {panelOpen && (
        <div
          className="fixed inset-x-3 bottom-3 top-3 z-[9998] flex max-h-[calc(100dvh-1.5rem)] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0b1220] text-[14px] text-slate-100 shadow-2xl sm:inset-auto sm:bottom-24 sm:right-6 sm:top-auto sm:h-auto sm:max-h-[min(85dvh,32rem)] sm:w-[22rem]"
          style={{ WebkitTextSizeAdjust: "100%", textSizeAdjust: "100%" }}
        >
          <header className="flex shrink-0 items-start gap-3 border-b border-white/5 px-4 pb-3 pt-4">
            <div
              className="h-10 w-10 shrink-0 rounded-full"
              style={{
                background:
                  "conic-gradient(from 210deg at 50% 50%, #38bdf8, #f8fafc, #0284c7, #38bdf8)",
                boxShadow: "inset 0 1px 6px rgba(255,255,255,0.4)",
              }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-[14px] font-semibold leading-5 tracking-tight">Omniweb AI</p>
              <p className="truncate text-[12px] leading-4 text-slate-400">{subtitle}</p>
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

          <div
            ref={transcriptRef}
            className="min-h-0 flex-1 touch-pan-y space-y-2 overflow-y-auto overscroll-contain px-4 py-3 text-[14px] leading-5 [-webkit-overflow-scrolling:touch]"
          >
            {errorMsg ? (
              <div className="rounded-lg border border-red-500/30 bg-red-950/80 px-3 py-2 text-[12px] leading-5 text-red-200">
                <span className="block break-words">{errorMsg}</span>
                <button
                  type="button"
                  className="mt-1 text-red-300 underline hover:text-red-100"
                  onClick={() => {
                    setErrorMsg("");
                    void (mode === "voice" ? onVoiceClick() : onTextMode());
                  }}
                >
                  Retry
                </button>
              </div>
            ) : null}
            {lines.length === 0 && !errorMsg && (
              <p className="text-[12px] leading-relaxed text-slate-500">
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
                <p className="mb-0.5 text-[10px] uppercase tracking-wide opacity-60">
                  {ln.role === "user" ? "You" : "Assistant"}
                </p>
                <p className="whitespace-pre-wrap break-words text-[14px] leading-5">{ln.content}</p>
              </div>
            ))}
          </div>

          <div className="shrink-0 px-4 pb-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Language</p>
            <div className="relative">
              <button
                type="button"
                onClick={() => setLangOpen((o) => !o)}
                disabled={sessionOn}
                className="flex w-full items-center justify-between gap-2 rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-left text-[14px] hover:bg-slate-900 disabled:opacity-50"
              >
                <span className="flex items-center gap-2 truncate">
                  <span className="text-[18px] leading-none">{selectedLang ? flagEmoji(selectedLang) : "🌐"}</span>
                  <span className="truncate">{selectedLang?.label || "English"}</span>
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
              </button>
              {langOpen && langs.length > 0 && (
                <ul className="absolute bottom-full z-10 mb-1 max-h-48 w-full overflow-auto rounded-xl border border-white/10 bg-[#0f172a] py-1 text-[14px] shadow-xl">
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

          <div className="flex shrink-0 gap-2 px-4 pb-3">
            <button
              type="button"
              onClick={() => void onVoiceClick()}
              disabled={connecting}
              className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-3 text-[14px] font-medium transition-all ${
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
              className={`flex-1 flex items-center justify-center gap-2 rounded-xl border border-white/10 py-3 text-[14px] font-medium transition-all ${
                mode === "text"
                  ? "bg-slate-800 text-white"
                  : "bg-slate-900/60 text-slate-300 hover:bg-slate-800"
              } disabled:opacity-60`}
            >
              <MessageCircle className="h-4 w-4" />
              Text
            </button>
          </div>

          <div className="flex shrink-0 items-end gap-2 border-t border-white/5 px-4 pb-4 pt-3">
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
              className="max-h-24 min-h-11 flex-1 resize-none rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-[14px] leading-5 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
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
            <div className="flex shrink-0 justify-center px-4 pb-3">
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
  );
}

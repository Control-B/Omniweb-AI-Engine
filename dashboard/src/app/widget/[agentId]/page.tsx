"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { RetellWebClient } from "retell-client-js-sdk";
import { Mic, MicOff, PhoneOff, Loader2, Volume2 } from "lucide-react";

/**
 * Voice widget — Retell WebRTC via ``retell-client-js-sdk``.
 *
 * URL: /widget/{clientId}
 *
 * ``agentId`` route param is the Omniweb ``client_id`` (UUID). The engine
 * resolves the Retell agent and returns a short-lived ``access_token``.
 */

type ConvStatus = "idle" | "connecting" | "connected" | "error";

function engineBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_ENGINE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

export default function VoiceWidgetPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const [convStatus, setConvStatus] = useState<ConvStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [micMuted, setMicMuted] = useState(false);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const clientRef = useRef<RetellWebClient | null>(null);

  useEffect(() => {
    const c = new RetellWebClient();
    clientRef.current = c;

    const onStarted = () => {
      setConvStatus("connected");
      setErrorMsg("");
    };
    const onEnded = () => {
      setConvStatus("idle");
      setAgentSpeaking(false);
    };
    const onError = (e: unknown) => {
      console.error("Retell error:", e);
      const msg =
        typeof e === "string"
          ? e
          : e && typeof e === "object" && "message" in e
            ? String((e as { message?: string }).message)
            : "Connection failed";
      setErrorMsg(msg);
      setConvStatus("error");
    };

    c.on("call_started", onStarted);
    c.on("call_ended", onEnded);
    c.on("error", onError);
    c.on("agent_start_talking", () => setAgentSpeaking(true));
    c.on("agent_stop_talking", () => setAgentSpeaking(false));

    return () => {
      try {
        c.stopCall();
      } catch {
        /* ignore */
      }
      clientRef.current = null;
    };
  }, []);

  const startSession = useCallback(async () => {
    if (!agentId) return;
    setConvStatus("connecting");
    setErrorMsg("");

    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });

      const res = await fetch(`${engineBaseUrl()}/api/retell/web-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: agentId }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || `HTTP ${res.status}`);
      }

      const data = (await res.json()) as { access_token: string };
      if (!data.access_token) {
        throw new Error("Missing access_token from engine");
      }

      const client = clientRef.current;
      if (!client) throw new Error("Retell client not ready");

      await client.startCall({ accessToken: data.access_token });
    } catch (err: unknown) {
      console.error("Failed to start session:", err);
      const e = err as { name?: string; message?: string };
      if (e?.name === "NotAllowedError" || e?.name === "PermissionDeniedError") {
        setErrorMsg("Microphone access is required. Please allow microphone access and try again.");
      } else {
        setErrorMsg(e?.message || "Failed to connect. Please try again.");
      }
      setConvStatus("error");
    }
  }, [agentId]);

  const endSession = useCallback(async () => {
    try {
      await clientRef.current?.stopCall();
    } catch {
      /* ignore */
    }
    setConvStatus("idle");
    setAgentSpeaking(false);
  }, []);

  const toggleMic = useCallback(() => {
    setMicMuted((prev) => !prev);
  }, []);

  const isActive = convStatus === "connected";
  const isConnecting = convStatus === "connecting";
  const isSpeaking = isActive && agentSpeaking;

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex flex-col items-center justify-center p-4 select-none">
      <div className="relative flex items-center justify-center mb-8">
        {isActive && isSpeaking && (
          <>
            <div className="absolute w-40 h-40 rounded-full bg-blue-500/10 animate-ping" style={{ animationDuration: "2s" }} />
            <div className="absolute w-32 h-32 rounded-full bg-blue-500/15 animate-ping" style={{ animationDuration: "1.5s", animationDelay: "0.3s" }} />
          </>
        )}
        {isActive && !isSpeaking && (
          <div className="absolute w-28 h-28 rounded-full bg-blue-500/10 animate-pulse" style={{ animationDuration: "3s" }} />
        )}

        <button
          onClick={isActive ? endSession : startSession}
          disabled={isConnecting}
          className={`
            relative z-10 w-24 h-24 rounded-full flex items-center justify-center
            transition-all duration-500 ease-out
            focus:outline-none focus:ring-2 focus:ring-blue-400/50 focus:ring-offset-2 focus:ring-offset-[#0a0a0f]
            ${isConnecting
              ? "bg-gradient-to-br from-blue-600/60 to-cyan-500/60 cursor-wait"
              : isActive
                ? isSpeaking
                  ? "bg-gradient-to-br from-blue-500 to-cyan-400 shadow-[0_0_40px_rgba(59,130,246,0.5)] scale-105"
                  : "bg-gradient-to-br from-blue-600 to-cyan-500 shadow-[0_0_25px_rgba(59,130,246,0.3)]"
                : "bg-gradient-to-br from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 hover:shadow-[0_0_30px_rgba(59,130,246,0.3)] hover:scale-105 cursor-pointer"
            }
          `}
          aria-label={isActive ? "End call" : "Start call"}
        >
          {isConnecting ? (
            <Loader2 className="w-8 h-8 text-white animate-spin" />
          ) : isActive ? (
            isSpeaking ? (
              <Volume2 className="w-8 h-8 text-white animate-pulse" />
            ) : (
              <Mic className="w-8 h-8 text-white" />
            )
          ) : (
            <Mic className="w-8 h-8 text-white" />
          )}
        </button>
      </div>

      <div className="text-center mb-6 min-h-[3rem]">
        {convStatus === "idle" && (
          <p className="text-white/80 text-sm font-medium">Tap to start talking</p>
        )}
        {isConnecting && (
          <p className="text-blue-300 text-sm font-medium animate-pulse">Connecting…</p>
        )}
        {isActive && isSpeaking && (
          <p className="text-cyan-300 text-sm font-medium">Agent is speaking…</p>
        )}
        {isActive && !isSpeaking && (
          <p className="text-white/70 text-sm font-medium">Listening…</p>
        )}
        {convStatus === "error" && (
          <div className="space-y-2">
            <p className="text-red-400 text-sm">{errorMsg}</p>
            <button
              type="button"
              onClick={startSession}
              className="text-xs text-blue-400 hover:text-blue-300 underline"
            >
              Try again
            </button>
          </div>
        )}
      </div>

      {isActive && (
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={toggleMic}
            className={`
              w-12 h-12 rounded-full flex items-center justify-center transition-all
              ${micMuted
                ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                : "bg-white/10 text-white/70 hover:bg-white/20 hover:text-white"
              }
            `}
            aria-label={micMuted ? "Unmute" : "Mute"}
          >
            {micMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>

          <button
            type="button"
            onClick={endSession}
            className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 hover:bg-red-500/30 flex items-center justify-center transition-all"
            aria-label="End call"
          >
            <PhoneOff className="w-5 h-5" />
          </button>
        </div>
      )}

      <div className="absolute bottom-4 text-[10px] text-white/20">
        Powered by Omniweb AI · Retell
      </div>
    </div>
  );
}

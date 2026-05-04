"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, Mic, MicOff, PhoneOff, Volume2 } from "lucide-react";
import { DeepgramVoiceAgentSession } from "@/lib/deepgramVoiceAgentClient";

/**
 * Voice-first widget page.
 *
 * Renders a compact, brand-free voice UI that connects to the current
 * Omniweb Deepgram voice agent runtime. No text input, no chat bubbles,
 * no expandable panels — just a mic orb and status text.
 *
 * URL: /widget/{agentId}
 *
 * Can be embedded in an iframe on any client website:
 *   <iframe src="https://engine.omniweb.ai/widget/{agentId}" ...>
 */

type ConvStatus = "idle" | "connecting" | "connected" | "error";

type DeepgramBootstrapResponse = {
  ok: boolean;
  client_id: string;
  agent_name: string;
  websocket_url: string;
  access_token: string;
  expires_in?: number;
  settings: Record<string, unknown>;
};

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
  const [isSpeaking, setIsSpeaking] = useState(false);
  const sessionRef = useRef<DeepgramVoiceAgentSession | null>(null);
  const isMountedRef = useRef(true);
  const apiBase = useMemo(() => engineBaseUrl(), []);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Start the voice session
  const startSession = useCallback(async () => {
    if (!agentId) return;
    setConvStatus("connecting");
    setErrorMsg("");

    try {
      const bootstrapRes = await fetch(`${apiBase}/api/deepgram/voice-agent/bootstrap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: agentId,
        }),
      });
      const bootstrapBody = (await bootstrapRes.json().catch(() => null)) as DeepgramBootstrapResponse | { detail?: string } | null;
      if (!bootstrapRes.ok || !bootstrapBody || !("access_token" in bootstrapBody)) {
        const detail = bootstrapBody && "detail" in bootstrapBody ? bootstrapBody.detail : undefined;
        throw new Error(detail || "Failed to initialize voice session");
      }

      const session = new DeepgramVoiceAgentSession({
        onStructuredMessage: (data) => {
          if (!isMountedRef.current) return;
          const type = String(data.type ?? "");
          if (type === "AgentStartedSpeaking") {
            setIsSpeaking(true);
          }
          if (type === "AgentAudioDone" || type === "AgentStoppedSpeaking" || type === "UserStartedSpeaking") {
            setIsSpeaking(false);
          }
        },
        onError: (message) => {
          if (!isMountedRef.current) return;
          setErrorMsg(message || "Voice session failed.");
          setConvStatus("error");
        },
        onClose: () => {
          if (!isMountedRef.current) return;
          sessionRef.current = null;
          setIsSpeaking(false);
          setConvStatus((current) => (current === "error" ? current : "idle"));
        },
      });

      sessionRef.current = session;
      await session.connect({
        websocketUrl: bootstrapBody.websocket_url,
        accessToken: bootstrapBody.access_token,
        settings: bootstrapBody.settings,
        enableMic: !micMuted,
      });

      if (!isMountedRef.current) {
        await session.disconnect();
        return;
      }

      setConvStatus("connected");
    } catch (err: unknown) {
      console.error("Failed to start session:", err);
      const error = err as { name?: string; message?: string };
      if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
        setErrorMsg("Microphone access is required. Please allow microphone access and try again.");
      } else {
        setErrorMsg(error.message || "Failed to connect. Please try again.");
      }
      setConvStatus("error");
    }
    }, [agentId, apiBase, micMuted]);

  // End the voice session
  const endSession = useCallback(async () => {
    try {
      await sessionRef.current?.disconnect();
    } catch {
      // ignore
    }
    sessionRef.current = null;
    setIsSpeaking(false);
    setConvStatus("idle");
  }, []);

  // Toggle mic mute
  const toggleMic = useCallback(() => {
    setMicMuted((prev) => {
      const next = !prev;
      sessionRef.current?.setMicrophoneEnabled(!next);
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      void sessionRef.current?.disconnect();
    };
  }, []);

  // Determine the visual state
  const isActive = convStatus === "connected";
  const isConnecting = convStatus === "connecting";

  if (!agentId) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4 text-center text-white/70">
        Invalid widget URL. Use `/widget/&lt;client-id&gt;`.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex flex-col items-center justify-center p-4 select-none">
      {/* Orb */}
      <div className="relative flex items-center justify-center mb-8">
        {/* Outer pulse rings */}
        {isActive && isSpeaking && (
          <>
            <div className="absolute w-40 h-40 rounded-full bg-blue-500/10 animate-ping" style={{ animationDuration: "2s" }} />
            <div className="absolute w-32 h-32 rounded-full bg-blue-500/15 animate-ping" style={{ animationDuration: "1.5s", animationDelay: "0.3s" }} />
          </>
        )}
        {isActive && !isSpeaking && (
          <div className="absolute w-28 h-28 rounded-full bg-blue-500/10 animate-pulse" style={{ animationDuration: "3s" }} />
        )}

        {/* Main orb button */}
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

      {/* Status text */}
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
              onClick={startSession}
              className="text-xs text-blue-400 hover:text-blue-300 underline"
            >
              Try again
            </button>
          </div>
        )}
      </div>

      {/* Controls (only shown when active) */}
      {isActive && (
        <div className="flex items-center gap-4">
          <button
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
            onClick={endSession}
            className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 hover:bg-red-500/30 flex items-center justify-center transition-all"
            aria-label="End call"
          >
            <PhoneOff className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Powered by */}
      <div className="absolute bottom-4 text-[10px] text-white/20">
        Powered by Omniweb AI
      </div>
    </div>
  );
}

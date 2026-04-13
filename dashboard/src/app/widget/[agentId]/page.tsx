"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { useConversation } from "@elevenlabs/react";
import { Mic, MicOff, PhoneOff, Loader2, Volume2 } from "lucide-react";

/**
 * Voice-first widget page.
 *
 * Renders a compact, brand-free voice UI that connects to an ElevenLabs
 * Conversational AI agent via WebRTC.  No text input, no chat bubbles,
 * no expandable panels — just a mic orb and status text.
 *
 * URL: /widget/{agentId}
 *
 * Can be embedded in an iframe on any client website:
 *   <iframe src="https://engine.omniweb.ai/widget/{agentId}" ...>
 */

type ConvStatus = "idle" | "connecting" | "connected" | "error";

export default function VoiceWidgetPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const [convStatus, setConvStatus] = useState<ConvStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [micMuted, setMicMuted] = useState(false);
  const [volume] = useState(1);
  const pulseRef = useRef<HTMLDivElement>(null);

  const conversation = useConversation({
    onConnect: () => {
      setConvStatus("connected");
      setErrorMsg("");
    },
    onDisconnect: () => {
      setConvStatus("idle");
    },
    onError: (error: any) => {
      console.error("ElevenLabs error:", error);
      setErrorMsg(typeof error === "string" ? error : error?.message || "Connection failed");
      setConvStatus("error");
    },
  });

  const { status, isSpeaking } = conversation;

  // Start the voice session
  const startSession = useCallback(async () => {
    if (!agentId) return;
    setConvStatus("connecting");
    setErrorMsg("");

    try {
      // Request mic permission first
      await navigator.mediaDevices.getUserMedia({ audio: true });

      await conversation.startSession({
        agentId,
      });
    } catch (err: any) {
      console.error("Failed to start session:", err);
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setErrorMsg("Microphone access is required. Please allow microphone access and try again.");
      } else {
        setErrorMsg(err.message || "Failed to connect. Please try again.");
      }
      setConvStatus("error");
    }
  }, [agentId, conversation]);

  // End the voice session
  const endSession = useCallback(async () => {
    try {
      await conversation.endSession();
    } catch {
      // ignore
    }
    setConvStatus("idle");
  }, [conversation]);

  // Toggle mic mute
  const toggleMic = useCallback(() => {
    setMicMuted((prev) => !prev);
  }, []);

  // Determine the visual state
  const isActive = convStatus === "connected";
  const isConnecting = convStatus === "connecting";

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

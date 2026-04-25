"use client";

import { useParams } from "next/navigation";
import { VoiceWidgetClient } from "../voice-widget-client";

function normalizeAgentId(raw: string | string[] | undefined): string | undefined {
  if (raw === undefined) return undefined;
  const v = Array.isArray(raw) ? raw[0] : raw;
  const s = typeof v === "string" ? v.trim() : "";
  return s || undefined;
}

export default function VoiceWidgetWithIdPage() {
  const params = useParams<{ agentId: string }>();
  const agentId = normalizeAgentId(params?.agentId);
  return <VoiceWidgetClient agentId={agentId} />;
}

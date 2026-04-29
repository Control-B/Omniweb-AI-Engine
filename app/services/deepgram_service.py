"""Deepgram — temporary browser tokens and Voice Agent settings helpers."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services.prompt_engine import compose_system_prompt

logger = get_logger(__name__)
settings = get_settings()

DEEPGRAM_GRANT_URL = "https://api.deepgram.com/v1/auth/grant"
DEEPGRAM_AGENT_WS_URL = "wss://agent.deepgram.com/v1/agent/converse"


async def grant_temporary_token(ttl_seconds: int = 600) -> dict[str, Any]:
    if not settings.deepgram_configured:
        raise RuntimeError("DEEPGRAM_API_KEY is not configured")

    ttl = max(30, min(int(ttl_seconds), 3600))
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            DEEPGRAM_GRANT_URL,
            headers={
                "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"ttl_seconds": ttl},
        )
        if resp.status_code >= 400:
            logger.error(
                "Deepgram auth/grant failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        return resp.json()


def _tts_voice_for_config(config: AgentConfig) -> str:
    voice_id = (config.voice_id or "").strip()
    if "aura" in voice_id.lower():
        return voice_id
    return settings.DEEPGRAM_TTS_VOICE


def _agent_language_tag(config: AgentConfig, requested: str | None = None) -> str:
    supported = [str(item).lower().strip() for item in (config.supported_languages or ["en"])]
    if requested:
        normalized = requested.lower().strip()
        if normalized == "multi":
            return "multi"
        if normalized in supported or any(lang.startswith(normalized) for lang in supported):
            return normalized[:8] if len(normalized) > 2 else normalized
    if len(supported) > 1:
        return "multi"
    if supported:
        return supported[0][:8]
    return "en"[:8]


def build_voice_agent_settings(config: AgentConfig, language: str | None = None) -> dict[str, Any]:
    composed = compose_system_prompt(
        agent_name=config.agent_name or "Alex",
        business_name=config.business_name or "",
        industry_slug=config.industry or "general",
        agent_mode=config.agent_mode,
        business_type=config.business_type,
        services=config.services or [],
        business_hours=config.business_hours or {},
        timezone=config.timezone or "America/New_York",
        booking_url=config.booking_url,
        after_hours_message=config.after_hours_message or "",
        custom_prompt=config.system_prompt,
        custom_guardrails=config.custom_guardrails or [],
        custom_escalation_triggers=config.custom_escalation_triggers or [],
        custom_context=config.custom_context,
    )
    language_tag = _agent_language_tag(config, language)
    tts_voice = _tts_voice_for_config(config)
    think_model = (config.llm_model or "").strip() or settings.DEEPGRAM_AGENT_MODEL

    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 16000},
            "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
        },
        "agent": {
            "language": language_tag,
            "listen": {"model": settings.DEEPGRAM_STT_MODEL},
            "think": {
                "provider": {"type": "open_ai"},
                "model": think_model,
                "prompt": composed,
            },
            "speak": {"model": tts_voice},
        },
    }


def transcript_lines_to_turns(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        role = str(line.get("role") or "user").strip().lower()
        content = str(line.get("content") or "").strip()
        if not content:
            continue
        speaker = "agent" if role == "assistant" else "caller"
        turns.append(
            {
                "speaker": speaker,
                "text": content,
                "timestamp": line.get("timestamp") or index,
            }
        )
    return turns


def summarize_transcript_fallback(turns: list[dict[str, Any]]) -> str | None:
    if not turns:
        return None

    caller_lines = [
        str(turn.get("text") or "").strip()
        for turn in turns
        if turn.get("speaker") == "caller"
    ]
    agent_lines = [
        str(turn.get("text") or "").strip()
        for turn in turns
        if turn.get("speaker") == "agent"
    ]
    caller_lines = [line for line in caller_lines if line]
    agent_lines = [line for line in agent_lines if line]

    if not caller_lines and not agent_lines:
        return None

    summary_parts: list[str] = []
    if caller_lines:
        summary_parts.append(f"Visitor asked about: {caller_lines[0][:180]}")
    if len(caller_lines) > 1:
        summary_parts.append(
            f"They exchanged {len(caller_lines)} visitor messages during the session"
        )
    if agent_lines:
        summary_parts.append(f"The assistant responded with guidance on {agent_lines[0][:140]}")

    return ". ".join(summary_parts).strip()[:500] or None


async def summarize_transcript(turns: list[dict[str, Any]]) -> str | None:
    if not turns:
        return None

    transcript_text = "\n".join(
        f"{str(turn.get('speaker') or 'unknown').upper()}: {str(turn.get('text') or '').strip()}"
        for turn in turns
        if str(turn.get("text") or "").strip()
    ).strip()
    if not transcript_text:
        return None

    if not settings.openai_configured:
        return summarize_transcript_fallback(turns)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You summarize website AI assistant conversations. Return JSON only "
                        "with keys: summary, sentiment. Keep summary to 1-2 sentences and "
                        "capture the user's goal and outcome."
                    ),
                },
                {"role": "user", "content": f"Transcript:\n{transcript_text}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=180,
        )
        raw = response.choices[0].message.content or "{}"
        payload = json.loads(raw)
        summary = str(payload.get("summary") or "").strip()
        if summary:
            return summary[:500]
        return summarize_transcript_fallback(turns)
    except Exception as exc:
        logger.warning("Deepgram widget summary generation failed", error=str(exc))
        return summarize_transcript_fallback(turns)
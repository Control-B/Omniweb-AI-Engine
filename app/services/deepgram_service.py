"""Deepgram — temporary browser tokens and Voice Agent settings helpers."""

from __future__ import annotations

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


async def grant_temporary_token(*, ttl_seconds: int = 600) -> dict[str, Any]:
    """Mint a short-lived JWT for browser Voice Agent / streaming APIs.

    Requires a Deepgram API key with at least Member role (see Deepgram token docs).
    """
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
    vid = (config.voice_id or "").strip()
    if "aura" in vid.lower():
        return vid
    return settings.DEEPGRAM_TTS_VOICE


def _agent_language_tag(config: AgentConfig, requested: str | None) -> str:
    """BCP-47-ish tag for Voice Agent ``agent.language`` (``multi`` when appropriate)."""
    supported = [str(x).lower().strip() for x in (config.supported_languages or ["en"])]
    if requested:
        r = requested.lower().strip()
        if r == "multi":
            return "multi"
        if r in supported or any(s.startswith(r) for s in supported):
            return r[:8] if len(r) > 2 else r
    if len(supported) > 1:
        return "multi"
    return (supported[0] if supported else "en")[:8]


def build_voice_agent_settings(
    config: AgentConfig,
    *,
    language: str | None = None,
) -> dict[str, Any]:
    """Build a Voice Agent ``Settings`` object (see Deepgram message-flow docs)."""
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
    lang_tag = _agent_language_tag(config, language)
    tts = _tts_voice_for_config(config)
    think_model = (config.llm_model or "").strip() or settings.DEEPGRAM_AGENT_MODEL

    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 16000},
            "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
        },
        "agent": {
            "language": lang_tag,
            "listen": {"model": settings.DEEPGRAM_STT_MODEL},
            "think": {
                "provider": {"type": "open_ai"},
                "model": think_model,
                "prompt": composed,
            },
            "speak": {"model": tts},
        },
    }

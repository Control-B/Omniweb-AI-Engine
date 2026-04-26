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
SUPPORTED_VOICE_LANGUAGE_CODES = {
    "en",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "ja",
    "ko",
    "zh",
    "hi",
    "ar",
    "nl",
    "pl",
    "ru",
    "tr",
    "uk",
    "multi",
}
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "hi": "Hindi",
    "ar": "Arabic",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "multi": "the visitor's language",
}


def _coerce_services(raw: Any) -> list[str]:
    """JSONB may be a list, legacy dict map, or empty; prompt code expects list[str]."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, dict):
        return [str(k).strip() for k in raw if str(k).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _coerce_business_hours(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_supported_languages(raw: Any) -> list[str]:
    if raw is None:
        return ["en"]
    if isinstance(raw, str):
        s = raw.strip().lower()
        return [s] if s else ["en"]
    if isinstance(raw, list):
        out = [str(x).lower().strip() for x in raw if str(x).strip()]
        return out if out else ["en"]
    return ["en"]


def _coerce_str_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, dict):
        return [str(v).strip() for v in raw.values() if str(v).strip()]
    return []


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
    if not vid:
        return settings.DEEPGRAM_TTS_VOICE
    if vid.lower() == "aura-asteria-en":
        return "aura-2-asteria-en"
    if "aura" in vid.lower():
        return vid
    return settings.DEEPGRAM_TTS_VOICE


def _deepgram_tts_for_language(lang_tag: str, config: AgentConfig) -> str:
    if lang_tag.lower().startswith("es"):
        return "aura-2-aquila-es"
    return _tts_voice_for_config(config)


def _elevenlabs_voice_for_config(config: AgentConfig) -> str:
    vid = (config.voice_id or "").strip()
    if vid and "aura" not in vid.lower():
        return vid
    return settings.ELEVENLABS_DEFAULT_VOICE_ID


def _agent_language_tag(config: AgentConfig, requested: str | None) -> str:
    """BCP-47-ish tag for Voice Agent ``agent.language`` (``multi`` when appropriate)."""
    supported = _coerce_supported_languages(config.supported_languages)
    if requested:
        r = requested.lower().strip()
        if r in SUPPORTED_VOICE_LANGUAGE_CODES:
            return r[:8] if len(r) > 2 else r
        if any(s.startswith(r) for s in supported):
            return r[:8] if len(r) > 2 else r
    if len(supported) > 1:
        return "multi"
    return (supported[0] if supported else "en")[:8]


def _language_name(lang_tag: str) -> str:
    return LANGUAGE_NAMES.get(lang_tag.lower().split("-")[0], lang_tag)


def _opening_greeting(config: AgentConfig) -> str:
    greeting = (config.agent_greeting or "").strip()
    if greeting:
        return greeting

    agent_name = (config.agent_name or "your AI assistant").strip()
    business_name = (config.business_name or "our business").strip()
    return f"Hello, this is {agent_name} from {business_name}. How can I help you today?"


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
        services=_coerce_services(config.services),
        business_hours=_coerce_business_hours(config.business_hours),
        timezone=config.timezone or "America/New_York",
        booking_url=config.booking_url,
        after_hours_message=config.after_hours_message or "",
        custom_prompt=config.system_prompt,
        custom_guardrails=_coerce_str_list(config.custom_guardrails),
        custom_escalation_triggers=_coerce_str_list(config.custom_escalation_triggers),
        custom_context=config.custom_context,
    )
    lang_tag = _agent_language_tag(config, language)
    opening_greeting = _opening_greeting(config)
    language_instruction = (
        f"\n\n## Voice Session Opening\n"
        f"CRITICAL LANGUAGE REQUIREMENT: The selected voice language is {_language_name(lang_tag)} ({lang_tag}). "
        f"Speak and respond only in {_language_name(lang_tag)} for this entire voice session. "
        f"Do not use English unless the selected voice language is English. "
        f"If the selected language is multi/the visitor's language, infer the visitor's language from speech and respond in that language.\n"
        f"The voice session must begin with this complete welcome message. Do not shorten it, "
        f"skip the agent name, skip the business name, or replace it with a generic greeting:\n"
        f"\"{opening_greeting}\"\n\n"
        f"If the selected language is not English, translate the full meaning of that welcome "
        f"message into {_language_name(lang_tag)} while preserving every identity and business detail. "
        f"After the welcome message, wait for the user."
    )
    think_model = (config.llm_model or "").strip() or settings.DEEPGRAM_AGENT_MODEL
    listen_language = "multi" if lang_tag == "multi" else lang_tag
    deepgram_speak = {
        "provider": {
            "type": "deepgram",
            "model": _deepgram_tts_for_language(lang_tag, config),
        }
    }
    speak: dict[str, Any] | list[dict[str, Any]]
    if settings.ELEVENLABS_API_KEY:
        eleven_voice_id = _elevenlabs_voice_for_config(config)
        language_code = "multi" if lang_tag == "multi" else lang_tag
        speak = [
            {
                "provider": {
                    "type": "eleven_labs",
                    "model_id": "eleven_turbo_v2_5",
                    "language_code": language_code,
                },
                "endpoint": {
                    "url": f"wss://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id}/multi-stream-input",
                    "headers": {"xi-api-key": settings.ELEVENLABS_API_KEY},
                },
            },
            deepgram_speak,
        ]
    else:
        speak = deepgram_speak

    # Shape must match Deepgram Voice Agent v1 Settings (see voice-agent-settings docs):
    # listen/speak/think use nested { "provider": { "type", "model", ... } }.
    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 16000},
            "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
        },
        "agent": {
            "language": lang_tag,
            "greeting": opening_greeting,
            "listen": {
                "provider": {
                    "type": "deepgram",
                    "model": settings.DEEPGRAM_STT_MODEL,
                    "language": listen_language,
                    "smart_format": False,
                }
            },
            "think": {
                "provider": {
                    "type": "open_ai",
                    "model": think_model,
                    "temperature": 0.7,
                },
                "prompt": f"{composed}{language_instruction}",
            },
            "speak": speak,
        },
    }

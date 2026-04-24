"""Deepgram service for public TTS utilities and language options."""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

BASE_URL = settings.DEEPGRAM_API_BASE_URL.rstrip("/")

SUPPORTED_LANGUAGE_OPTIONS: list[dict[str, Any]] = [
    {"code": "de", "label": "German", "model": "aura-2-viktoria-de"},
    {"code": "en", "label": "English", "model": "aura-2-thalia-en"},
    {"code": "es", "label": "Spanish", "model": "aura-2-celeste-es"},
    {"code": "fr", "label": "French", "model": "aura-2-agathe-fr"},
]

LANGUAGE_MODEL_MAP = {item["code"]: item["model"] for item in SUPPORTED_LANGUAGE_OPTIONS}


def _normalize_language_code(language: str | None) -> str:
    if not language:
        return settings.DEEPGRAM_DEFAULT_LANGUAGE
    return language.strip().lower().replace("_", "-").split("-", 1)[0]


def resolve_tts_model(*, language: str | None = None, voice_id: str | None = None) -> str:
    normalized = _normalize_language_code(language)
    return voice_id or LANGUAGE_MODEL_MAP.get(normalized) or settings.DEEPGRAM_DEFAULT_TTS_MODEL


def get_language_options() -> list[dict[str, Any]]:
    default_language = _normalize_language_code(settings.DEEPGRAM_DEFAULT_LANGUAGE)
    options: list[dict[str, Any]] = []

    for item in SUPPORTED_LANGUAGE_OPTIONS:
        code = item["code"]
        model = resolve_tts_model(language=code)
        options.append(
            {
                **item,
                "voice_id": model,
                "configured": settings.deepgram_configured or code == default_language,
                "default": code == default_language,
            }
        )

    return options


async def synthesize_speech(
    *,
    text: str,
    language: str | None = None,
    voice_id: str | None = None,
) -> bytes:
    if not settings.deepgram_configured:
        raise RuntimeError("DEEPGRAM_API_KEY is not configured")

    model = resolve_tts_model(language=language, voice_id=voice_id)
    url = f"{BASE_URL}/speak"
    params = {"model": model}
    headers = {
        "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"text": text}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, params=params, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Deepgram TTS failed (%s): %s", response.status_code, response.text)
            raise RuntimeError("Deepgram TTS request failed") from exc
        return response.content

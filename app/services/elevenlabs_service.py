"""Minimal ElevenLabs compatibility service.

This module preserves the ElevenLabs API surface still referenced by the
backend routes and provisioning flows after the Retell migration cleanup.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

BASE_URL = "https://api.elevenlabs.io/v1"
CONVAI_URL = f"{BASE_URL}/convai"
TTS_URL = f"{BASE_URL}/text-to-speech"
SARAH_ELEVENLABS_VOICE_ID = "nf4MCGNSdM0hxM95ZBQR"
LEGACY_DEFAULT_ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"

SUPPORTED_LANGUAGE_OPTIONS: list[dict[str, Any]] = [
    {"code": "en", "label": "English", "flag": "🇺🇸"},
    {"code": "es", "label": "Spanish", "flag": "🇪🇸"},
    {"code": "fr", "label": "French", "flag": "🇫🇷"},
    {"code": "de", "label": "German", "flag": "🇩🇪"},
    {"code": "it", "label": "Italian", "flag": "🇮🇹"},
    {"code": "pt", "label": "Portuguese", "flag": "🇧🇷"},
    {"code": "nl", "label": "Dutch", "flag": "🇳🇱"},
    {"code": "sv", "label": "Swedish", "flag": "🇸🇪"},
    {"code": "ro", "label": "Romanian", "flag": "🇷🇴"},
    {"code": "ru", "label": "Russian", "flag": "🇷🇺"},
    {"code": "uk", "label": "Ukrainian", "flag": "🇺🇦"},
    {"code": "pl", "label": "Polish", "flag": "🇵🇱"},
    {"code": "ar", "label": "Arabic", "flag": "🇸🇦", "rtl": True},
    {"code": "tr", "label": "Turkish", "flag": "🇹🇷"},
    {"code": "hi", "label": "Hindi", "flag": "🇮🇳"},
    {"code": "bn", "label": "Bengali", "flag": "🇧🇩"},
    {"code": "zh", "label": "Chinese", "flag": "🇨🇳"},
    {"code": "ja", "label": "Japanese", "flag": "🇯🇵"},
    {"code": "ko", "label": "Korean", "flag": "🇰🇷"},
    {"code": "id", "label": "Indonesian", "flag": "🇮🇩"},
    {"code": "vi", "label": "Vietnamese", "flag": "🇻🇳"},
    {"code": "tl", "label": "Filipino", "flag": "🇵🇭"},
    {"code": "sw", "label": "Swahili", "flag": "🇰🇪"},
]


def _normalize_language_code(language: str | None) -> str:
    if not language:
        return settings.ELEVENLABS_DEFAULT_LANGUAGE
    return language.strip().lower().replace("_", "-").split("-", 1)[0]


def _voice_id_for_language(language: str | None) -> str | None:
    normalized = _normalize_language_code(language)
    env_key = f"ELEVENLABS_VOICE_ID_{normalized.upper()}"
    return getattr(settings, env_key, None) or None


def resolve_voice_id(*, language: str | None = None, voice_id: str | None = None) -> str:
    resolved = voice_id or _voice_id_for_language(language) or settings.ELEVENLABS_DEFAULT_VOICE_ID
    return SARAH_ELEVENLABS_VOICE_ID if resolved == LEGACY_DEFAULT_ELEVENLABS_VOICE_ID else resolved


def get_language_options() -> list[dict[str, Any]]:
    default_language = _normalize_language_code(settings.ELEVENLABS_DEFAULT_LANGUAGE)
    return [
        {
            **item,
            "voice_id": resolve_voice_id(language=item["code"]),
            "configured": bool(_voice_id_for_language(item["code"])) or item["code"] == default_language,
            "default": item["code"] == default_language,
        }
        for item in SUPPORTED_LANGUAGE_OPTIONS
    ]


def _headers(*, accept: str | None = None) -> dict[str, str]:
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    if accept:
        headers["Accept"] = accept
    return headers


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30, headers=_headers())


async def synthesize_speech(
    *,
    text: str,
    language: str | None = None,
    voice_id: str | None = None,
    model_id: str = "eleven_turbo_v2_5",
) -> bytes:
    if not settings.ELEVENLABS_API_KEY:
        raise RuntimeError("ElevenLabs is not configured")

    selected_voice_id = resolve_voice_id(language=language, voice_id=voice_id)
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.32,
            "similarity_boost": 0.78,
            "style": 0.55,
            "use_speaker_boost": True,
        },
    }

    async with httpx.AsyncClient(timeout=45, headers=_headers(accept="audio/mpeg")) as http:
        response = await http.post(f"{TTS_URL}/{selected_voice_id}", json=payload)
        response.raise_for_status()
        return response.content


async def import_twilio_phone_number(
    *,
    phone_number: str,
    label: str,
    twilio_account_sid: str,
    twilio_auth_token: str,
    agent_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "phone_number": phone_number,
        "label": label,
        "sid": twilio_account_sid,
        "token": twilio_auth_token,
    }

    if not settings.ELEVENLABS_API_KEY:
        logger.info("[STUB] Would import Twilio number into ElevenLabs", phone_number=phone_number)
        return {"phone_number_id": f"phone_stub_{uuid.uuid4().hex[:12]}"}

    async with _client() as http:
        response = await http.post(f"{CONVAI_URL}/phone-numbers", json=payload)
        response.raise_for_status()
        data = response.json()
        phone_number_id = data["phone_number_id"]
        logger.info("Imported Twilio number into ElevenLabs", phone_number=phone_number, phone_number_id=phone_number_id)
        if agent_id:
            await assign_phone_to_agent(phone_number_id, agent_id)
        return data


async def assign_phone_to_agent(phone_number_id: str, agent_id: str) -> dict[str, Any]:
    if not settings.ELEVENLABS_API_KEY:
        return {"phone_number_id": phone_number_id, "agent_id": agent_id}

    async with _client() as http:
        response = await http.patch(
            f"{CONVAI_URL}/phone-numbers/{phone_number_id}",
            json={"agent_id": agent_id},
        )
        response.raise_for_status()
        return response.json()


async def delete_phone_number(phone_number_id: str) -> bool:
    if not settings.ELEVENLABS_API_KEY:
        return True

    async with _client() as http:
        response = await http.delete(f"{CONVAI_URL}/phone-numbers/{phone_number_id}")
        return response.status_code in (200, 204, 404)


async def list_conversations(
    *,
    agent_id: str | None = None,
    page_size: int = 30,
    cursor: str | None = None,
) -> dict[str, Any]:
    if not settings.ELEVENLABS_API_KEY:
        return {"conversations": [], "has_more": False, "next_cursor": None}

    params: dict[str, Any] = {"page_size": page_size}
    if agent_id:
        params["agent_id"] = agent_id
    if cursor:
        params["cursor"] = cursor

    async with _client() as http:
        response = await http.get(f"{CONVAI_URL}/conversations", params=params)
        response.raise_for_status()
        return response.json()


def get_widget_embed_code(agent_id: str) -> dict[str, str]:
    platform_url = settings.PLATFORM_URL.rstrip("/")
    widget_url = f"{platform_url}/widget/{agent_id}"
    iframe = (
        f'<iframe\n'
        f'  src="{widget_url}"\n'
        f'  width="120"\n'
        f'  height="120"\n'
        f'  style="position:fixed;bottom:20px;right:20px;border:none;border-radius:50%;z-index:9999;overflow:hidden;"\n'
        f'  allow="microphone"\n'
        f'  title="Voice Assistant"\n'
        f'></iframe>'
    )
    legacy = (
        f'<elevenlabs-convai agent-id="{agent_id}"></elevenlabs-convai>\n'
        f'<script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>'
    )
    return {"iframe": iframe, "legacy": legacy, "widget_url": widget_url}

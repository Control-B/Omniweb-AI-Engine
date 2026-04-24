"""Retell service for AI telephony agents, numbers, and call lookups."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
BASE_URL = settings.RETELL_API_BASE_URL.rstrip("/")

DEFAULT_WEBHOOK_EVENTS = ["call_started", "call_ended", "call_analyzed"]
LANGUAGE_MAP = {
    "de": "de-DE",
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "it": "it-IT",
    "ja": "ja-JP",
    "nl": "nl-NL",
    "pt": "pt-BR",
}


def _require_config() -> None:
    if not settings.RETELL_API_KEY:
        raise RuntimeError("RETELL_API_KEY is not configured")
    if not settings.RETELL_LLM_ID:
        raise RuntimeError("RETELL_LLM_ID is not configured")
    if not settings.RETELL_DEFAULT_VOICE_ID:
        raise RuntimeError("RETELL_DEFAULT_VOICE_ID is not configured")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.RETELL_API_KEY}",
        "Content-Type": "application/json",
    }


def _normalize_language(language: str | None, supported_languages: list[str] | None = None) -> str:
    if supported_languages and len(supported_languages) > 1:
        return "multi"
    normalized = (language or settings.RETELL_DEFAULT_LANGUAGE).strip().lower().replace("_", "-").split("-", 1)[0]
    return LANGUAGE_MAP.get(normalized, settings.RETELL_DEFAULT_LANGUAGE)


def _webhook_url() -> str:
    configured = settings.RETELL_WEBHOOK_URL.strip()
    if configured:
        return configured
    engine_base = getattr(settings, "ENGINE_BASE_URL", settings.APP_BASE_URL).rstrip("/")
    return f"{engine_base}/api/webhooks/retell"


async def _request(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    _require_config()
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.request(method, url, headers=_headers(), json=json_body)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Retell API failed %s %s (%s): %s", method, path, response.status_code, response.text)
            raise RuntimeError(f"Retell API request failed for {path}") from exc
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()


async def create_agent(
    *,
    agent_name: str,
    language: str | None = None,
    supported_languages: list[str] | None = None,
    voice_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "agent_name": agent_name,
        "response_engine": {
            "type": "retell-llm",
            "llm_id": settings.RETELL_LLM_ID,
        },
        "voice_id": voice_id or settings.RETELL_DEFAULT_VOICE_ID,
        "language": _normalize_language(language, supported_languages),
        "webhook_url": _webhook_url(),
        "webhook_events": DEFAULT_WEBHOOK_EVENTS,
        "begin_message_delay_ms": 800,
        "responsiveness": 0.7,
        "interruption_sensitivity": 0.85,
        "enable_backchannel": False,
        "reminder_max_count": 0,
        "denoising_mode": "noise-and-background-speech-cancellation",
        "data_storage_setting": "everything",
        "analysis_summary_prompt": "Summarize the call outcome in 2-3 sentences, including the user intent, requested action, and agreed next step.",
        "analysis_user_sentiment_prompt": "Return the user's overall sentiment as Positive, Neutral, or Negative based on the full interaction.",
    }
    return await _request("POST", "/create-agent", json_body=payload)


async def update_agent(
    agent_id: str,
    *,
    agent_name: str,
    language: str | None = None,
    supported_languages: list[str] | None = None,
    voice_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "agent_name": agent_name,
        "response_engine": {
            "type": "retell-llm",
            "llm_id": settings.RETELL_LLM_ID,
        },
        "voice_id": voice_id or settings.RETELL_DEFAULT_VOICE_ID,
        "language": _normalize_language(language, supported_languages),
        "webhook_url": _webhook_url(),
        "webhook_events": DEFAULT_WEBHOOK_EVENTS,
        "begin_message_delay_ms": 800,
        "responsiveness": 0.7,
        "interruption_sensitivity": 0.85,
        "enable_backchannel": False,
        "reminder_max_count": 0,
        "denoising_mode": "noise-and-background-speech-cancellation",
        "data_storage_setting": "everything",
        "analysis_summary_prompt": "Summarize the call outcome in 2-3 sentences, including the user intent, requested action, and agreed next step.",
        "analysis_user_sentiment_prompt": "Return the user's overall sentiment as Positive, Neutral, or Negative based on the full interaction.",
    }
    return await _request("PATCH", f"/update-agent/{agent_id}", json_body=payload)


async def get_agent(agent_id: str) -> dict[str, Any]:
    _require_config()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BASE_URL}/get-agent/{agent_id}", headers=_headers())
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Retell get agent failed (%s): %s", response.status_code, response.text)
            raise RuntimeError("Failed to fetch Retell agent") from exc
        return response.json()


async def create_phone_number(
    *,
    phone_number: str,
    agent_id: str,
    agent_version: int | None = None,
    nickname: str,
    area_code: int | None = None,
    country_code: str = "US",
    number_provider: str = "twilio",
    toll_free: bool = False,
) -> dict[str, Any]:
    weight = 1.0
    agent_binding = {
        "agent_id": agent_id,
        "weight": weight,
    }
    if agent_version is not None:
        agent_binding["agent_version"] = agent_version

    payload: dict[str, Any] = {
        "phone_number": phone_number,
        "nickname": nickname,
        "country_code": country_code,
        "number_provider": number_provider,
        "toll_free": toll_free,
        "inbound_agents": [agent_binding],
        "outbound_agents": [agent_binding],
    }
    if area_code is not None:
        payload["area_code"] = area_code

    return await _request("POST", "/create-phone-number", json_body=payload)


async def update_phone_number(
    phone_number: str,
    *,
    agent_id: str,
    agent_version: int | None = None,
    nickname: str | None = None,
) -> dict[str, Any]:
    agent_binding = {
        "agent_id": agent_id,
        "weight": 1.0,
    }
    if agent_version is not None:
        agent_binding["agent_version"] = agent_version

    payload: dict[str, Any] = {
        "inbound_agents": [agent_binding],
        "outbound_agents": [agent_binding],
    }
    if nickname:
        payload["nickname"] = nickname

    return await _request("PATCH", f"/update-phone-number/{phone_number}", json_body=payload)


async def delete_phone_number(phone_number: str) -> None:
    await _request("DELETE", f"/delete-phone-number/{phone_number}")


async def get_call(call_id: str) -> dict[str, Any]:
    _require_config()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BASE_URL}/v2/get-call/{call_id}", headers=_headers())
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Retell get call failed (%s): %s", response.status_code, response.text)
            raise RuntimeError("Failed to fetch Retell call") from exc
        return response.json()


async def create_web_call(
    *,
    agent_id: str,
    agent_version: int | None = None,
    metadata: dict[str, Any] | None = None,
    dynamic_variables: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent_id": agent_id,
    }
    if agent_version is not None:
        payload["agent_version"] = agent_version
    if metadata:
        payload["metadata"] = metadata
    if dynamic_variables:
        payload["retell_llm_dynamic_variables"] = dynamic_variables
    return await _request("POST", "/v2/create-web-call", json_body=payload)


def verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    if not settings.RETELL_API_KEY:
        logger.warning("RETELL_API_KEY not set; skipping Retell webhook verification")
        return True
    if not signature_header:
        return False

    signature_parts = {}
    for raw_part in signature_header.split(","):
        if "=" not in raw_part:
            continue
        key, value = raw_part.split("=", 1)
        signature_parts[key.strip()] = value.strip()

    timestamp = signature_parts.get("v")
    digest = signature_parts.get("d")
    if not timestamp or not digest:
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    if abs(int(time.time()) - timestamp_int) > 300:
        logger.warning("Retell webhook rejected due to stale timestamp")
        return False

    expected = hmac.new(
        settings.RETELL_API_KEY.encode(),
        body + timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, digest)

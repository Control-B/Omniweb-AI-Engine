"""Retell AI service helpers.

Provides the small Retell API surface still used by the live FastAPI routes:
web-call token minting, outbound phone calls, and agent patching.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

RETELL_API_BASE = "https://api.retellai.com"


def _headers() -> dict[str, str]:
    key = settings.RETELL_API_KEY
    if not key:
        return {}
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def create_web_call(*, agent_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.RETELL_API_KEY:
        raise RuntimeError("RETELL_API_KEY is not configured")

    body: dict[str, Any] = {"agent_id": agent_id}
    if metadata:
        body["metadata"] = metadata

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{RETELL_API_BASE}/v2/create-web-call",
            headers=_headers(),
            json=body,
        )
        if response.status_code >= 400:
            logger.error(
                "Retell create-web-call failed",
                status=response.status_code,
                body=response.text[:500],
            )
            response.raise_for_status()
        data = response.json()
        logger.info("Retell web call created", agent_id=agent_id, call_id=data.get("call_id"))
        return data


async def create_phone_call(
    *,
    agent_id: str,
    from_number: str,
    to_number: str,
    metadata: dict[str, Any] | None = None,
    dynamic_variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.RETELL_API_KEY:
        raise RuntimeError("RETELL_API_KEY is not configured")

    body: dict[str, Any] = {
        "from_number": from_number,
        "to_number": to_number,
        "override_agent_id": agent_id,
    }
    if metadata:
        body["metadata"] = metadata
    if dynamic_variables:
        body["retell_llm_dynamic_variables"] = dynamic_variables

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{RETELL_API_BASE}/v2/create-phone-call",
            headers=_headers(),
            json=body,
        )
        if response.status_code >= 400:
            logger.error(
                "Retell create-phone-call failed",
                status=response.status_code,
                body=response.text[:500],
            )
            response.raise_for_status()
        data = response.json()
        logger.info("Retell phone call created", agent_id=agent_id, call_id=data.get("call_id"))
        return data


async def patch_agent(agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.RETELL_API_KEY:
        raise RuntimeError("RETELL_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.patch(
            f"{RETELL_API_BASE}/update-agent/{agent_id}",
            headers=_headers(),
            content=json.dumps(payload),
        )
        if response.status_code >= 400:
            logger.error(
                "Retell update-agent failed",
                agent_id=agent_id,
                status=response.status_code,
                body=response.text[:500],
            )
            response.raise_for_status()
        return response.json()


def map_locale_to_retell_language(supported: list[str]) -> str:
    if not supported:
        return "en-US"
    if len(supported) > 1:
        return "multi"

    code = (supported[0] or "en").lower().strip()
    mapping = {
        "en": "en-US",
        "es": "es-419",
        "fr": "fr-FR",
        "de": "de-DE",
        "it": "it-IT",
        "pt": "pt-BR",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "zh": "zh-CN",
        "hi": "hi-IN",
        "ar": "ar-SA",
        "nl": "nl-NL",
        "pl": "pl-PL",
        "ru": "ru-RU",
        "tr": "tr-TR",
    }
    return mapping.get(code, "en-US")
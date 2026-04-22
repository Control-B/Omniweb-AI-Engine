"""Retell AI — web calls, agent updates, and webhook verification.

Omniweb orchestrates Retell agents (created in Retell or via API). The engine
mints short-lived web call tokens and syncs high-level agent settings.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

RETELL_API_BASE = "https://api.retellai.com"


def verify_webhook_signature(*, raw_body: str, signature_header: str | None, api_key: str) -> bool:
    """Verify ``X-Retell-Signature`` per Retell docs (HMAC-SHA256 of body + timestamp)."""
    if not signature_header or not api_key:
        return False
    m = re.match(r"v=(\d+),d=(.+)", signature_header.strip())
    if not m:
        return False
    ts_str, digest_hex = m.group(1), m.group(2).strip()
    try:
        ts_ms = int(ts_str)
    except ValueError:
        return False
    if abs(int(time.time() * 1000) - ts_ms) > 5 * 60 * 1000:
        return False
    payload = (raw_body + ts_str).encode("utf-8")
    expected = hmac.new(api_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected.lower(), digest_hex.lower())
    except Exception:
        return False


def _headers() -> dict[str, str]:
    key = settings.RETELL_API_KEY
    if not key:
        return {}
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def create_web_call(*, agent_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a Retell web call and return access_token for the browser SDK."""
    if not settings.RETELL_API_KEY:
        raise RuntimeError("RETELL_API_KEY is not configured")

    body: dict[str, Any] = {"agent_id": agent_id}
    if metadata:
        body["metadata"] = metadata

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{RETELL_API_BASE}/v2/create-web-call",
            headers=_headers(),
            json=body,
        )
        if resp.status_code >= 400:
            logger.error(
                "Retell create-web-call failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        data = resp.json()
        logger.info("Retell web call created", agent_id=agent_id, call_id=data.get("call_id"))
        return data


async def patch_agent(agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """PATCH ``/update-agent/{agent_id}`` (partial update)."""
    if not settings.RETELL_API_KEY:
        raise RuntimeError("RETELL_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.patch(
            f"{RETELL_API_BASE}/update-agent/{agent_id}",
            headers=_headers(),
            content=json.dumps(payload),
        )
        if resp.status_code >= 400:
            logger.error(
                "Retell update-agent failed",
                agent_id=agent_id,
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        return resp.json()


def map_locale_to_retell_language(supported: list[str]) -> str:
    """Pick Retell ``language`` field: ``multi`` if several locales, else a BCP-47 tag."""
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


def language_options_public() -> list[dict[str, str]]:
    """Locales surfaced to landing / widget UIs (subset of Retell-supported)."""
    return [
        {"code": "en", "label": "English (default)", "retell": "en-US"},
        {"code": "es", "label": "Spanish", "retell": "es-419"},
        {"code": "fr", "label": "French", "retell": "fr-FR"},
        {"code": "de", "label": "German", "retell": "de-DE"},
        {"code": "it", "label": "Italian", "retell": "it-IT"},
        {"code": "pt", "label": "Portuguese (Brazil)", "retell": "pt-BR"},
        {"code": "ja", "label": "Japanese", "retell": "ja-JP"},
        {"code": "ko", "label": "Korean", "retell": "ko-KR"},
        {"code": "zh", "label": "Chinese", "retell": "zh-CN"},
        {"code": "hi", "label": "Hindi", "retell": "hi-IN"},
        {"code": "multi", "label": "Multilingual (auto)", "retell": "multi"},
    ]

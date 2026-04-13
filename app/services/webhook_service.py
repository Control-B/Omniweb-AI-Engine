"""Webhook event delivery service.

Fires HTTP POST requests to tenant-configured webhook URLs when events occur:
  - lead.created      — new lead extracted from a conversation
  - lead.qualified    — lead scored above threshold
  - call.completed    — call ended and post-call processing finished
  - call.started      — new inbound/outbound call began

Each event is signed with HMAC-SHA256 so the receiver can verify authenticity.
Failed deliveries are logged with status code and error for debugging.
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Client, WebhookEvent

logger = get_logger(__name__)
settings = get_settings()

# ── Event types ──────────────────────────────────────────────────────────────

EVENT_LEAD_CREATED = "lead.created"
EVENT_LEAD_QUALIFIED = "lead.qualified"
EVENT_CALL_COMPLETED = "call.completed"
EVENT_CALL_STARTED = "call.started"

VALID_EVENTS = {EVENT_LEAD_CREATED, EVENT_LEAD_QUALIFIED, EVENT_CALL_COMPLETED, EVENT_CALL_STARTED}

# ── Signing ──────────────────────────────────────────────────────────────────


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook verification."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _build_headers(payload_bytes: bytes, secret: str | None, event: str) -> dict:
    """Build webhook delivery headers including signature."""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Omniweb-Webhooks/1.0",
        "X-Omniweb-Event": event,
        "X-Omniweb-Delivery": str(uuid.uuid4()),
        "X-Omniweb-Timestamp": str(int(time.time())),
    }
    if secret:
        sig = _sign_payload(payload_bytes, secret)
        headers["X-Omniweb-Signature"] = f"sha256={sig}"
    return headers


# ── Core delivery ────────────────────────────────────────────────────────────


async def fire_webhook(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    event: str,
    data: dict[str, Any],
) -> Optional["WebhookEvent"]:
    """Fire a webhook event to the client's configured URL.

    Returns the WebhookEvent log record, or None if no URL configured.
    """
    if event not in VALID_EVENTS:
        logger.warning(f"Unknown webhook event type: {event}")
        return None

    # Look up client's webhook URL
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client or not client.crm_webhook_url:
        return None

    url = client.crm_webhook_url.strip()
    if not url:
        return None

    # Build payload
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    payload_bytes = json.dumps(payload, default=str).encode()

    # Build signed headers
    webhook_secret = getattr(client, "webhook_secret", None)
    headers = _build_headers(payload_bytes, webhook_secret, event)

    # Create log record
    log = WebhookEvent(
        id=uuid.uuid4(),
        client_id=client_id,
        event=event,
        url=url,
        payload=payload,
        status="pending",
    )
    db.add(log)
    await db.flush()

    # Deliver
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(url, content=payload_bytes, headers=headers)
            log.status_code = resp.status_code
            if resp.is_success:
                log.status = "delivered"
                logger.info(f"Webhook {event} delivered to {url} → {resp.status_code}")
            else:
                log.status = "failed"
                log.error_message = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
                logger.warning(f"Webhook {event} failed for {url}: HTTP {resp.status_code}")
    except httpx.TimeoutException:
        log.status = "failed"
        log.error_message = "Request timed out (15s)"
        logger.warning(f"Webhook {event} timed out for {url}")
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)[:500]
        logger.warning(f"Webhook {event} error for {url}: {exc}")

    await db.flush()
    return log


# ── Convenience helpers ──────────────────────────────────────────────────────


async def fire_lead_created(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    lead: Any,
    call: Any = None,
) -> Optional["WebhookEvent"]:
    """Fire lead.created event with full lead data."""
    data: dict[str, Any] = {
        "lead": {
            "id": str(lead.id),
            "caller_name": lead.caller_name,
            "caller_phone": lead.caller_phone,
            "caller_email": lead.caller_email,
            "intent": lead.intent,
            "urgency": lead.urgency,
            "summary": lead.summary,
            "services_requested": lead.services_requested,
            "lead_score": lead.lead_score,
            "status": lead.status,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        },
    }
    if call:
        data["call"] = {
            "id": str(call.id),
            "caller_number": call.caller_number,
            "direction": call.direction,
            "channel": call.channel,
            "duration_seconds": call.duration_seconds,
        }
    return await fire_webhook(db, client_id=client_id, event=EVENT_LEAD_CREATED, data=data)


async def fire_lead_qualified(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    lead: Any,
) -> Optional["WebhookEvent"]:
    """Fire lead.qualified event when a lead scores above threshold."""
    data = {
        "lead": {
            "id": str(lead.id),
            "caller_name": lead.caller_name,
            "caller_phone": lead.caller_phone,
            "caller_email": lead.caller_email,
            "intent": lead.intent,
            "urgency": lead.urgency,
            "summary": lead.summary,
            "services_requested": lead.services_requested,
            "lead_score": lead.lead_score,
            "status": lead.status,
        },
    }
    return await fire_webhook(db, client_id=client_id, event=EVENT_LEAD_QUALIFIED, data=data)


async def fire_call_completed(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    call: Any,
    lead: Any = None,
    transcript_turns: int = 0,
) -> Optional["WebhookEvent"]:
    """Fire call.completed event when a call finishes processing."""
    data: dict[str, Any] = {
        "call": {
            "id": str(call.id),
            "caller_number": call.caller_number,
            "direction": call.direction,
            "channel": call.channel,
            "status": call.status,
            "duration_seconds": call.duration_seconds,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "transcript_turns": transcript_turns,
        },
    }
    if lead:
        data["lead"] = {
            "id": str(lead.id),
            "caller_name": lead.caller_name,
            "caller_phone": lead.caller_phone,
            "caller_email": lead.caller_email,
            "intent": lead.intent,
            "urgency": lead.urgency,
            "lead_score": lead.lead_score,
            "summary": lead.summary,
        }
    return await fire_webhook(db, client_id=client_id, event=EVENT_CALL_COMPLETED, data=data)


async def fire_call_started(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    call: Any,
) -> Optional["WebhookEvent"]:
    """Fire call.started event when a new call begins."""
    data = {
        "call": {
            "id": str(call.id),
            "caller_number": call.caller_number,
            "direction": call.direction,
            "channel": call.channel,
            "started_at": call.started_at.isoformat() if call.started_at else None,
        },
    }
    return await fire_webhook(db, client_id=client_id, event=EVENT_CALL_STARTED, data=data)


async def test_webhook(
    url: str,
    secret: str | None = None,
) -> dict:
    """Send a test ping to a webhook URL. Returns delivery result."""
    payload = {
        "event": "webhook.test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "message": "This is a test webhook from Omniweb. If you received this, your webhook is configured correctly!",
        },
    }
    payload_bytes = json.dumps(payload, default=str).encode()
    headers = _build_headers(payload_bytes, secret, "webhook.test")

    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.post(url, content=payload_bytes, headers=headers)
            return {
                "ok": resp.is_success,
                "status_code": resp.status_code,
                "message": f"Delivered successfully (HTTP {resp.status_code})" if resp.is_success else f"Failed with HTTP {resp.status_code}",
            }
    except httpx.TimeoutException:
        return {"ok": False, "status_code": None, "message": "Request timed out (10s)"}
    except Exception as exc:
        return {"ok": False, "status_code": None, "message": str(exc)}

"""Twilio service — SMS and voice routing.

Twilio is used for:
  - SMS follow-ups after calls
  - Voice call forwarding (when number is in "forward" mode)

AI voice calls are handled by Retell after you connect numbers in the Retell dashboard.
"""
from typing import Optional

from twilio.rest import Client
from twilio.request_validator import RequestValidator

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _client() -> Client:
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


async def send_sms(
    to_number: str,
    from_number: str,
    body: str,
    status_callback_url: Optional[str] = None,
) -> dict:
    """Send an SMS message via Twilio.

    Returns {"sid": ..., "status": ..., "error": None} or {"error": "..."}
    """
    if not settings.twilio_configured:
        logger.info(f"[STUB] SMS to {to_number}: {body[:80]}")
        return {"sid": "SM_stub", "status": "stub", "error": None}
    try:
        client = _client()
        kwargs = dict(to=to_number, from_=from_number, body=body)
        if status_callback_url:
            kwargs["status_callback"] = status_callback_url
        msg = client.messages.create(**kwargs)
        return {"sid": msg.sid, "status": msg.status, "error": None}
    except Exception as exc:
        logger.error(f"SMS failed to {to_number}: {exc}")
        return {"sid": None, "status": "failed", "error": str(exc)}


async def set_voice_forwarding(
    twilio_sid: str,
    forward_to: str,
) -> dict:
    """Configure a Twilio number to forward calls to another phone number.

    Uses a TwiML Bin-style URL with inline TwiML that <Dial>s the target number.
    """
    if not settings.twilio_configured:
        logger.info(f"[STUB] Would set forwarding on {twilio_sid} → {forward_to}")
        return {"ok": True, "stub": True}
    try:
        client = _client()
        # Use Twilio's Twimlet echo service for simple TwiML hosting
        from urllib.parse import quote
        twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Dial>{forward_to}</Dial></Response>'
        voice_url = f"https://twimlets.com/echo?Twiml={quote(twiml)}"
        incoming = client.incoming_phone_numbers(twilio_sid).update(
            voice_url=voice_url,
        )
        logger.info(f"Set forwarding on {twilio_sid} → {forward_to}")
        return {"ok": True, "sid": incoming.sid}
    except Exception as exc:
        logger.error(f"Failed to set forwarding on {twilio_sid}: {exc}")
        return {"ok": False, "error": str(exc)}


async def clear_voice_config(
    twilio_sid: str,
) -> dict:
    """Clear voice URL from a Twilio number (before attaching to another provider)."""
    if not settings.twilio_configured:
        logger.info(f"[STUB] Would clear voice config on {twilio_sid}")
        return {"ok": True, "stub": True}
    try:
        client = _client()
        incoming = client.incoming_phone_numbers(twilio_sid).update(
            voice_url="",
        )
        logger.info(f"Cleared voice config on {twilio_sid}")
        return {"ok": True, "sid": incoming.sid}
    except Exception as exc:
        logger.error(f"Failed to clear voice config on {twilio_sid}: {exc}")
        return {"ok": False, "error": str(exc)}


def validate_twilio_request(
    url: str,
    post_params: dict,
    twilio_signature: str,
) -> bool:
    """Verify an inbound Twilio SMS webhook request signature."""
    if not settings.twilio_configured:
        return True
    try:
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        return validator.validate(url, post_params, twilio_signature)
    except Exception as exc:
        logger.warning(f"Twilio request validation error: {exc}")
        return False

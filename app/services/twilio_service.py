"""Twilio service — SMS ONLY.

Twilio is used exclusively for SMS follow-ups after calls.
There is NO voice, NO TwiML, NO SIP, NO Twilio webhooks for voice.
All real-time voice is handled by ElevenLabs Conversational AI.
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

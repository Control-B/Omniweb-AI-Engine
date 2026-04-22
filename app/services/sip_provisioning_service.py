"""Phone Number Provisioning — Twilio purchase and basic routing.

Retell handles AI telephony once you connect the Twilio number in the Retell
dashboard (SIP / native integration). This service only buys/releases numbers
and configures simple Twilio forwarding when ``mode == forward``.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import PhoneNumber

logger = get_logger(__name__)
settings = get_settings()


async def provision_new_number(
    db: AsyncSession,
    *,
    client_id: str,
    phone_number: str,
    friendly_name: str,
    retell_agent_id: str | None = None,
    area_code: str | None = None,
) -> PhoneNumber:
    """Buy a Twilio number and persist it. ``retell_agent_id`` is informational only."""
    _ = retell_agent_id
    _ = area_code
    logger.info(f"Provisioning number {phone_number} for client {client_id}")

    twilio_sid = await _buy_twilio_number(phone_number, friendly_name)

    number_record = PhoneNumber(
        client_id=client_id,
        phone_number=phone_number,
        friendly_name=friendly_name,
        twilio_sid=twilio_sid,
        elevenlabs_phone_number_id=None,
        is_active=True,
        area_code=(phone_number[2:5] if phone_number.startswith("+1") else None),
        country="US",
    )
    db.add(number_record)
    await db.commit()
    await db.refresh(number_record)

    logger.info(f"Provisioned number {phone_number}: twilio_sid={twilio_sid}")
    return number_record


async def list_available_numbers(
    area_code: str | None = None,
    country: str = "US",
    limit: int = 20,
    number_type: str = "local",
) -> list[dict]:
    """Search available phone numbers from Twilio."""
    if not settings.twilio_configured:
        return [
            {"phone_number": "+15550000001", "location": "New York, NY", "monthly_rate": 2.00, "type": "local"},
            {"phone_number": "+15550000002", "location": "Los Angeles, CA", "monthly_rate": 2.00, "type": "local"},
        ]

    try:
        from twilio.rest import Client as TwilioClient

        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        kwargs: dict = {"limit": limit}
        if area_code:
            kwargs["area_code"] = area_code

        avail = client.available_phone_numbers(country)
        if number_type == "toll_free":
            numbers = avail.toll_free.list(**kwargs)
            rate = 3.00
        else:
            numbers = avail.local.list(**kwargs)
            rate = 2.00

        return [
            {
                "phone_number": n.phone_number,
                "friendly_name": n.friendly_name,
                "location": f"{n.locality}, {n.region}"
                if hasattr(n, "locality") and n.locality
                else (n.region if hasattr(n, "region") and n.region else ""),
                "capabilities": {
                    "voice": n.capabilities.get("voice", False),
                    "sms": n.capabilities.get("sms", False),
                },
                "monthly_rate": rate,
                "type": number_type,
            }
            for n in numbers
        ]
    except Exception as exc:
        logger.error(f"list_available_numbers failed: {exc}")
        return []


async def deprovision_number(
    db: AsyncSession,
    number: PhoneNumber,
    release_twilio_number: bool = False,
) -> None:
    """Mark inactive and optionally release the Twilio number."""
    if release_twilio_number and number.twilio_sid and settings.twilio_configured:
        try:
            from twilio.rest import Client as TwilioClient

            client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.incoming_phone_numbers(number.twilio_sid).delete()
            logger.info(f"Released Twilio number {number.phone_number}")
        except Exception as exc:
            logger.warning(f"Failed to release Twilio number {number.twilio_sid}: {exc}")

    number.is_active = False
    await db.commit()
    logger.info(f"Deprovisioned number {number.phone_number}")


async def set_number_mode(
    db: AsyncSession,
    number: PhoneNumber,
    mode: str,
    forward_to: str | None = None,
    retell_agent_id: str | None = None,
) -> None:
    """``forward`` configures Twilio PSTN forwarding. ``ai`` clears forwarding — bind AI in Retell."""
    from app.services import twilio_service

    _ = retell_agent_id

    if mode == "forward":
        if not forward_to:
            raise ValueError("forward_to is required when mode is 'forward'")
        result = await twilio_service.set_voice_forwarding(number.twilio_sid, forward_to)
        if not result.get("ok"):
            raise RuntimeError(f"Failed to set forwarding: {result.get('error')}")
        number.mode = "forward"
        number.forward_to = forward_to
    elif mode == "ai":
        await twilio_service.clear_voice_config(number.twilio_sid)
        number.mode = "ai"
        number.forward_to = None
        logger.info(
            "AI mode: finish inbound setup in Retell (connect this Twilio number to your Retell agent)."
        )
    else:
        raise ValueError(f"Invalid mode: {mode}")

    await db.commit()
    logger.info(f"Set {number.phone_number} to mode={mode}")


async def _buy_twilio_number(phone_number: str, friendly_name: str) -> str:
    """Purchase a phone number from Twilio. Returns the Twilio SID."""
    if not settings.twilio_configured:
        import uuid

        logger.info(f"[STUB] Would buy Twilio number {phone_number}")
        return f"PN_stub_{uuid.uuid4().hex[:12]}"

    try:
        from twilio.rest import Client as TwilioClient

        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        incoming = client.incoming_phone_numbers.create(
            phone_number=phone_number,
            friendly_name=friendly_name,
            voice_receive_mode="voice",
        )
        logger.info(f"Bought Twilio number {phone_number}: {incoming.sid}")
        return incoming.sid
    except Exception as exc:
        logger.error(f"Failed to buy Twilio number {phone_number}: {exc}")
        raise RuntimeError(f"Failed to buy {phone_number} from Twilio: {exc}") from exc

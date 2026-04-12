"""Phone Number Provisioning Service — Twilio + ElevenLabs lifecycle.

Provisioning flow:

  1. Buy a phone number from Twilio (Twilio owns the number)
  2. Import the Twilio number into ElevenLabs Conversational AI
  3. ElevenLabs re-configures Twilio to route calls to ElevenLabs agent
  4. Assign the ElevenLabs phone number to the client's agent
  5. Save the record to our DB

Deprovisioning:
  1. Remove the phone number from ElevenLabs
  2. Optionally release the number from Twilio
  3. Mark the DB record as inactive
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import PhoneNumber
from app.services import elevenlabs_service

logger = get_logger(__name__)
settings = get_settings()


async def provision_new_number(
    db: AsyncSession,
    *,
    client_id: str,
    phone_number: str,
    friendly_name: str,
    elevenlabs_agent_id: str | None = None,
    area_code: str | None = None,
) -> PhoneNumber:
    """Buy a Twilio number and import it into ElevenLabs.

    Args:
        client_id: UUID of the client this number belongs to
        phone_number: E.164 number to purchase e.g. "+15551234567"
        friendly_name: Human label e.g. "Bob's Plumbing Main Line"
        elevenlabs_agent_id: ElevenLabs agent ID to assign the number to
        area_code: Optional preferred area code for number search

    Returns PhoneNumber ORM instance (already saved to DB).
    """
    logger.info(f"Provisioning number {phone_number} for client {client_id}")

    # Step 1: Buy the number from Twilio
    twilio_sid = await _buy_twilio_number(phone_number, friendly_name)

    # Step 2: Import into ElevenLabs
    el_result = await elevenlabs_service.import_twilio_phone_number(
        phone_number=phone_number,
        label=friendly_name,
        twilio_account_sid=settings.TWILIO_ACCOUNT_SID,
        twilio_auth_token=settings.TWILIO_AUTH_TOKEN,
        agent_id=elevenlabs_agent_id,
    )
    elevenlabs_phone_id = el_result.get("phone_number_id", "")

    # Step 3: Persist to database
    number_record = PhoneNumber(
        client_id=client_id,
        phone_number=phone_number,
        friendly_name=friendly_name,
        twilio_sid=twilio_sid,
        elevenlabs_phone_number_id=elevenlabs_phone_id,
        is_active=True,
        area_code=(phone_number[2:5] if phone_number.startswith("+1") else None),
        country="US",
    )
    db.add(number_record)
    await db.commit()
    await db.refresh(number_record)

    logger.info(
        f"Provisioned number {phone_number}: "
        f"twilio_sid={twilio_sid} elevenlabs_phone_id={elevenlabs_phone_id}"
    )
    return number_record


async def list_available_numbers(
    area_code: str | None = None,
    country: str = "US",
    limit: int = 20,
) -> list[dict]:
    """Search available phone numbers from Twilio."""
    if not settings.twilio_configured:
        return [
            {"phone_number": "+15550000001", "location": "New York, NY", "monthly_rate": 1.15},
            {"phone_number": "+15550000002", "location": "Los Angeles, CA", "monthly_rate": 1.15},
        ]

    try:
        from twilio.rest import Client as TwilioClient

        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        kwargs = {"limit": limit}
        if area_code:
            kwargs["area_code"] = area_code

        if country == "US":
            numbers = client.available_phone_numbers("US").local.list(**kwargs)
        else:
            numbers = client.available_phone_numbers(country).local.list(**kwargs)

        return [
            {
                "phone_number": n.phone_number,
                "friendly_name": n.friendly_name,
                "location": f"{n.locality}, {n.region}" if n.locality else n.region or "",
                "capabilities": {
                    "voice": n.capabilities.get("voice", False),
                    "sms": n.capabilities.get("sms", False),
                },
                "monthly_rate": 1.15,
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
    """Remove a number from ElevenLabs and optionally release from Twilio."""
    # Remove from ElevenLabs
    if number.elevenlabs_phone_number_id:
        await elevenlabs_service.delete_phone_number(number.elevenlabs_phone_number_id)

    # Optionally release from Twilio
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
    elevenlabs_agent_id: str | None = None,
) -> None:
    """Switch a phone number between 'ai' and 'forward' mode.

    - ai mode: ElevenLabs handles calls (re-import into ElevenLabs if needed)
    - forward mode: Twilio forwards calls to `forward_to` phone number
    """
    from app.services import twilio_service

    if mode == "forward":
        if not forward_to:
            raise ValueError("forward_to is required when mode is 'forward'")

        # Step 1: Remove from ElevenLabs so it stops intercepting calls
        if number.elevenlabs_phone_number_id:
            try:
                await elevenlabs_service.delete_phone_number(number.elevenlabs_phone_number_id)
                logger.info(f"Removed {number.phone_number} from ElevenLabs for forward mode")
            except Exception as exc:
                logger.warning(f"Failed to remove from ElevenLabs: {exc}")

        # Step 2: Configure Twilio to forward calls
        result = await twilio_service.set_voice_forwarding(number.twilio_sid, forward_to)
        if not result.get("ok"):
            raise RuntimeError(f"Failed to set forwarding: {result.get('error')}")

        number.mode = "forward"
        number.forward_to = forward_to
        number.elevenlabs_phone_number_id = None  # No longer in ElevenLabs

    elif mode == "ai":
        # Step 1: Clear Twilio voice URL so ElevenLabs can take over
        await twilio_service.clear_voice_config(number.twilio_sid)

        # Step 2: Re-import into ElevenLabs
        el_result = await elevenlabs_service.import_twilio_phone_number(
            phone_number=number.phone_number,
            label=number.friendly_name or "AI Line",
            twilio_account_sid=settings.TWILIO_ACCOUNT_SID,
            twilio_auth_token=settings.TWILIO_AUTH_TOKEN,
            agent_id=elevenlabs_agent_id,
        )
        number.elevenlabs_phone_number_id = el_result.get("phone_number_id", "")
        number.mode = "ai"
        number.forward_to = None

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
        raise RuntimeError(f"Failed to buy {phone_number} from Twilio: {exc}")

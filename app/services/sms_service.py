"""SMS service — send and log SMS messages for clients.

Wraps TwilioService with DB logging and template rendering.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import SmsMessage, PhoneNumber, Client, Lead
from app.services import twilio_service

logger = get_logger(__name__)
settings = get_settings()


class SMSService:
    """Send SMS messages and log them to the DB."""

    @staticmethod
    async def send_and_log(
        db: AsyncSession,
        *,
        client_id: uuid.UUID,
        call_id: Optional[uuid.UUID],
        to_number: str,
        body: str,
        from_number: Optional[str] = None,
    ) -> SmsMessage:
        """Send an SMS via Twilio and save the record to the DB.

        from_number defaults to the client's first active phone number,
        then falls back to the global TWILIO_FROM_NUMBER.
        """
        if not from_number:
            from_number = await SMSService._get_client_from_number(db, client_id)

        # Send via Twilio
        result = await twilio_service.send_sms(
            to_number=to_number,
            from_number=from_number,
            body=body,
            status_callback_url=f"{settings.APP_BASE_URL}/webhooks/twilio/sms-status",
        )

        twilio_sid = None
        status = "failed"
        error = None

        if result:
            twilio_sid = result.get("sid")
            status = result.get("status", "sent")
        else:
            error = "Twilio send failed"

        # Log to DB
        sms = SmsMessage(
            id=uuid.uuid4(),
            client_id=client_id,
            call_id=call_id,
            direction="outbound",
            to_number=to_number,
            from_number=from_number,
            body=body,
            twilio_sid=twilio_sid,
            status=status,
            error_message=error,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(sms)
        await db.flush()
        return sms

    @staticmethod
    async def send_post_call_followup(
        db: AsyncSession,
        *,
        client_id: uuid.UUID,
        call_id: uuid.UUID,
        lead: Lead,
        agent_config: dict,
    ) -> Optional[SmsMessage]:
        """Send the standard post-call follow-up SMS to the caller.

        Template variables available: {caller_name}, {business_name}, {booking_url}
        """
        if not lead.caller_phone:
            return None

        business_name = agent_config.get("business_name", "us")
        caller_name = lead.caller_name or "there"
        booking_url = agent_config.get("booking_url", "")

        if booking_url:
            body = (
                f"Hi {caller_name}! Thanks for calling {business_name}. "
                f"Ready to book? {booking_url} — or reply to this text and we'll call you back."
            )
        else:
            body = (
                f"Hi {caller_name}! Thanks for calling {business_name}. "
                f"We'll follow up with you shortly. Reply STOP to opt out."
            )

        return await SMSService.send_and_log(
            db,
            client_id=client_id,
            call_id=call_id,
            to_number=lead.caller_phone,
            body=body,
        )

    @staticmethod
    async def send_missed_call_alert(
        db: AsyncSession,
        *,
        client_id: uuid.UUID,
        call_id: uuid.UUID,
        caller_phone: str,
        agent_config: dict,
    ) -> Optional[SmsMessage]:
        """Notify the caller that their call was missed and someone will follow up."""
        business_name = agent_config.get("business_name", "us")
        body = (
            f"Hi! You just called {business_name} but we missed your call. "
            f"We'll give you a ring back soon. Reply STOP to opt out."
        )
        return await SMSService.send_and_log(
            db,
            client_id=client_id,
            call_id=call_id,
            to_number=caller_phone,
            body=body,
        )

    @staticmethod
    async def _get_client_from_number(
        db: AsyncSession, client_id: uuid.UUID
    ) -> str:
        """Get the client's first active phone number, or fall back to global."""
        from sqlalchemy import select
        result = await db.execute(
            select(PhoneNumber)
            .where(PhoneNumber.client_id == client_id, PhoneNumber.is_active == True)
            .limit(1)
        )
        phone = result.scalar_one_or_none()
        if phone:
            return phone.phone_number
        return settings.TWILIO_FROM_NUMBER or "+10000000000"

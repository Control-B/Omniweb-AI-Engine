"""Outreach sequence service — automated multi-step follow-up campaigns.

Sequences are triggered by events (after_call, missed_call, new_lead).
Each step has a delay_minutes and sends an SMS (or future: email/call).
"""
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import OutreachSequence, Lead, Client, AgentConfig, Call
from app.services.sms_service import SMSService

logger = get_logger(__name__)
settings = get_settings()


class OutreachService:
    """Trigger and execute outreach sequences per client."""

    @staticmethod
    async def trigger_sequence(
        db: AsyncSession,
        *,
        client_id: uuid.UUID,
        trigger: str,  # after_call | missed_call | new_lead | manual
        lead: Optional[Lead] = None,
        call_id: Optional[uuid.UUID] = None,
    ) -> int:
        """Find all active sequences for this trigger and enqueue their steps.

        Returns the number of sequences triggered.
        """
        result = await db.execute(
            select(OutreachSequence).where(
                OutreachSequence.client_id == client_id,
                OutreachSequence.trigger == trigger,
                OutreachSequence.is_active == True,
            )
        )
        sequences = result.scalars().all()

        # Load agent config for template variables
        config_result = await db.execute(
            select(AgentConfig).where(AgentConfig.client_id == client_id)
        )
        config = config_result.scalar_one_or_none()
        config_dict = {
            "business_name": config.business_name if config else "",
            "booking_url": config.booking_url if config else "",
            "agent_name": config.agent_name if config else "Alex",
        }

        # Load client phone number
        from app.services.sms_service import SMSService
        from_number = await SMSService._get_client_from_number(db, client_id)

        count = 0
        for seq in sequences:
            for step in seq.steps:
                if not isinstance(step, dict):
                    continue
                step_type = step.get("type", "sms")
                delay_min = step.get("delay_minutes", 0)
                template = step.get("template", "")

                if step_type == "sms" and lead and lead.caller_phone and template:
                    # Schedule via asyncio (for low-volume; in production use ARQ/Redis)
                    asyncio.create_task(
                        OutreachService._send_delayed_sms(
                            client_id=client_id,
                            call_id=call_id,
                            to_number=lead.caller_phone,
                            from_number=from_number,
                            template=template,
                            delay_seconds=delay_min * 60,
                            context={
                                "name": lead.caller_name or "there",
                                **config_dict,
                            },
                        )
                    )
                    count += 1

        logger.info(f"Triggered {count} outreach steps for client {client_id} ({trigger})")
        return count

    @staticmethod
    async def _send_delayed_sms(
        *,
        client_id: uuid.UUID,
        call_id: Optional[uuid.UUID],
        to_number: str,
        from_number: str,
        template: str,
        delay_seconds: int,
        context: dict,
    ) -> None:
        """Wait delay_seconds then send a rendered SMS template."""
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        # Render template
        try:
            body = template.format(**context)
        except (KeyError, ValueError):
            body = template  # Send raw if template rendering fails

        from app.services.twilio_service import TwilioService
        result = await TwilioService.send_sms(
            to_number=to_number,
            from_number=from_number,
            body=body,
        )
        if result:
            logger.info(f"Outreach SMS sent to {to_number}: {result.get('sid')}")
        else:
            logger.warning(f"Outreach SMS failed to {to_number}")

    # ── CRUD for sequences ───────────────────────────────────────────────────

    @staticmethod
    async def create_sequence(
        db: AsyncSession,
        *,
        client_id: uuid.UUID,
        name: str,
        trigger: str,
        steps: list[dict],
    ) -> OutreachSequence:
        seq = OutreachSequence(
            id=uuid.uuid4(),
            client_id=client_id,
            name=name,
            trigger=trigger,
            steps=steps,
            is_active=True,
        )
        db.add(seq)
        await db.flush()
        await db.refresh(seq)
        return seq

    @staticmethod
    async def get_sequences(
        db: AsyncSession,
        client_id: uuid.UUID,
    ) -> list[OutreachSequence]:
        result = await db.execute(
            select(OutreachSequence).where(OutreachSequence.client_id == client_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def default_sequences_for_client(
        db: AsyncSession,
        client_id: uuid.UUID,
        business_name: str,
    ) -> list[OutreachSequence]:
        """Create the default outreach sequences for a newly onboarded client."""
        defaults = [
            {
                "name": "After-Call Follow-Up",
                "trigger": "after_call",
                "steps": [
                    {
                        "type": "sms",
                        "delay_minutes": 1,
                        "template": "Hi {name}! Thanks for calling {business_name}. We'll be in touch shortly. Want to book? {booking_url}",
                    },
                ],
            },
            {
                "name": "Missed Call Recovery",
                "trigger": "missed_call",
                "steps": [
                    {
                        "type": "sms",
                        "delay_minutes": 2,
                        "template": "Hi! You just called {business_name} but we missed you. We'd love to help — reply here or call us back anytime.",
                    },
                ],
            },
        ]

        created = []
        for d in defaults:
            seq = await OutreachService.create_sequence(
                db,
                client_id=client_id,
                name=d["name"],
                trigger=d["trigger"],
                steps=d["steps"],
            )
            created.append(seq)

        logger.info(f"Created {len(created)} default outreach sequences for client {client_id}")
        return created

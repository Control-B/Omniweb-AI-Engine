"""Post-call processing service.

After a call ends (ElevenLabs post-conversation webhook), this service:
1. Saves the full transcript to the DB
2. Runs the transcript through the LLM to extract a lead
3. Calculates lead score and urgency
4. Creates the Lead record
5. Triggers SMS follow-up
6. Fires CRM webhook if client has one configured
7. Marks the call as processed
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Call, Client, Transcript, Lead, AgentConfig
from app.services.sms_service import SMSService
from app.services.lead_qualification_engine import extract_lead_from_transcript

logger = get_logger(__name__)
settings = get_settings()


class PostCallService:
    """Process a completed call — transcript, lead, follow-up."""

    @staticmethod
    async def process(
        db: AsyncSession,
        *,
        call_id: uuid.UUID,
        turns: list[dict],  # [{"speaker": "agent"|"caller", "text": "...", "timestamp": "..."}]
        collected_data: Optional[dict] = None,  # data extracted by the agent during the call
    ) -> Optional[Lead]:
        """Full post-call pipeline. Returns the created Lead (or None if no lead extracted)."""

        # 1. Load call + client
        call_result = await db.execute(
            select(Call).where(Call.id == call_id)
        )
        call = call_result.scalar_one_or_none()
        if not call:
            logger.error(f"Post-call processing: Call {call_id} not found")
            return None

        config_result = await db.execute(
            select(AgentConfig).where(AgentConfig.client_id == call.client_id)
        )
        agent_config = config_result.scalar_one_or_none()
        config_dict = PostCallService._config_to_dict(agent_config) if agent_config else {}

        # 2. Save transcript
        await PostCallService._save_transcript(db, call=call, turns=turns)

        # 3. Extract lead via LLM (industry-aware)
        transcript_text = PostCallService._turns_to_text(turns)
        industry_slug = config_dict.get("industry", "general")

        lead_data = await PostCallService._extract_lead(
            transcript_text=transcript_text,
            caller_number=call.caller_number,
            collected_data=collected_data or {},
            industry_slug=industry_slug,
            business_name=config_dict.get("business_name", ""),
        )

        lead = None
        if lead_data:
            # 4. Create Lead record
            lead = Lead(
                id=uuid.uuid4(),
                call_id=call_id,
                client_id=call.client_id,
                caller_name=lead_data.get("caller_name"),
                caller_phone=call.caller_number,
                caller_email=lead_data.get("caller_email"),
                intent=lead_data.get("intent"),
                urgency=lead_data.get("urgency", "medium"),
                summary=lead_data.get("summary"),
                services_requested=lead_data.get("services_requested", []),
                status="new",
                lead_score=lead_data.get("lead_score", 0.5),
                follow_up_sent=False,
            )
            db.add(lead)
            await db.flush()
            await db.refresh(lead)
            logger.info(
                f"Lead created for call {call_id}: {lead.caller_name} — {lead.intent} "
                f"(score: {lead.lead_score:.2f}, urgency: {lead.urgency})"
            )

            # 5. Send SMS follow-up
            if config_dict.get("after_hours_sms_enabled", True):
                await SMSService.send_post_call_followup(
                    db,
                    client_id=call.client_id,
                    call_id=call_id,
                    lead=lead,
                    agent_config=config_dict,
                )

        # 6. Fire CRM webhook
        client_result = await db.execute(
            select(Client).where(Client.id == call.client_id)
        )
        client = client_result.scalar_one_or_none()
        if client and client.crm_webhook_url and lead:
            await PostCallService._fire_crm_webhook(
                url=client.crm_webhook_url,
                call=call,
                lead=lead,
                turns=turns,
            )
            call.crm_webhook_fired = True

        # 7. Mark call processed
        call.post_call_processed = True
        await db.flush()

        return lead

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    async def _save_transcript(
        db: AsyncSession,
        *,
        call: Call,
        turns: list[dict],
    ) -> Transcript:
        # Check if transcript already exists (idempotent)
        existing = await db.execute(
            select(Transcript).where(Transcript.call_id == call.id)
        )
        transcript = existing.scalar_one_or_none()

        if transcript:
            transcript.turns = turns
        else:
            transcript = Transcript(
                id=uuid.uuid4(),
                call_id=call.id,
                client_id=call.client_id,
                turns=turns,
            )
            db.add(transcript)

        await db.flush()
        return transcript

    @staticmethod
    def _turns_to_text(turns: list[dict]) -> str:
        """Convert JSONB turns into a readable transcript string for the LLM."""
        lines = []
        for t in turns:
            speaker = t.get("speaker", "unknown").upper()
            text = t.get("text", "").strip()
            if text:
                lines.append(f"{speaker}: {text}")
        return "\n".join(lines)

    @staticmethod
    async def _fire_crm_webhook(
        *,
        url: str,
        call: "Call",
        lead: Lead,
        turns: list[dict],
    ) -> None:
        """POST lead + call data to the client's CRM webhook URL."""
        payload = {
            "event": "new_lead",
            "call_id": str(call.id),
            "client_id": str(call.client_id),
            "caller_phone": call.caller_number,
            "direction": call.direction,
            "duration_seconds": call.duration_seconds,
            "lead": {
                "id": str(lead.id),
                "caller_name": lead.caller_name,
                "caller_phone": lead.caller_phone,
                "intent": lead.intent,
                "urgency": lead.urgency,
                "summary": lead.summary,
                "services_requested": lead.services_requested,
                "lead_score": lead.lead_score,
                "status": lead.status,
            },
            "transcript_turns": len(turns),
        }
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.post(url, json=payload)
                resp.raise_for_status()
                logger.info(f"CRM webhook fired to {url}: {resp.status_code}")
        except Exception as exc:
            logger.warning(f"CRM webhook failed for {url}: {exc}")

    @staticmethod
    def _config_to_dict(config: Optional[AgentConfig]) -> dict:
        if not config:
            return {}
        return {
            "agent_name": config.agent_name,
            "business_name": config.business_name,
            "business_type": config.business_type,
            "industry": getattr(config, "industry", "general"),
            "agent_mode": getattr(config, "agent_mode", "lead_qualifier"),
            "timezone": config.timezone,
            "booking_url": config.booking_url,
            "services": config.services,
            "after_hours_sms_enabled": config.after_hours_sms_enabled,
            "system_prompt": config.system_prompt,
            "voice_id": config.voice_id,
        }

    @staticmethod
    async def _extract_lead(
        *,
        transcript_text: str,
        caller_number: str,
        collected_data: dict,
        industry_slug: str,
        business_name: str,
    ) -> Optional[dict]:
        """Industry-aware lead extraction — delegates to lead_qualification_engine."""
        return await extract_lead_from_transcript(
            transcript_text=transcript_text,
            industry_slug=industry_slug,
            caller_number=caller_number,
            collected_data=collected_data,
            business_name=business_name,
        )

"""ElevenLabs Webhook Handler — receives post-conversation events.

ElevenLabs fires webhooks when conversations end. Configure in the
ElevenLabs dashboard → Agent → Platform Settings → Webhooks.

Webhook URL: https://api.yourdomain.com/webhooks/elevenlabs

Events:
  - post_conversation: Fired after a conversation completes.
    Contains: agent_id, conversation_id, transcript, metadata, analysis.

Security:
  Verified via the webhook secret configured in ElevenLabs dashboard.
  ElevenLabs sends it as a header: `X-ElevenLabs-Signature`.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AsyncSessionLocal
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, Call, PhoneNumber
from app.services import elevenlabs_service
from app.services.post_call_service import PostCallService

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/webhooks/elevenlabs", tags=["webhooks"])


def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify the ElevenLabs webhook signature."""
    secret = settings.ELEVENLABS_WEBHOOK_SECRET
    if not secret:
        logger.warning("ELEVENLABS_WEBHOOK_SECRET not set — skipping verification")
        return True
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("")
async def elevenlabs_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Receive post-conversation events from ElevenLabs.

    ElevenLabs sends a POST with JSON body after each conversation ends.
    """
    body = await request.body()
    signature = request.headers.get("X-ElevenLabs-Signature", "")

    if not _verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type", "post_conversation")
    agent_id = event.get("agent_id", "")
    conversation_id = event.get("conversation_id", "")

    logger.info(f"ElevenLabs webhook: {event_type} agent={agent_id} conv={conversation_id}")

    if event_type in ("post_conversation", "conversation.ended"):
        background_tasks.add_task(
            _handle_post_conversation,
            event=event,
        )
    else:
        logger.debug(f"Unhandled ElevenLabs event type: {event_type}")

    return {"ok": True}


async def _handle_post_conversation(event: dict) -> None:
    """Process a completed conversation — save call, transcript, extract lead.

    1. Find the client by the agent_id
    2. Create/update the Call record
    3. Extract transcript turns
    4. Run post-call pipeline (lead extraction, SMS, CRM webhook)
    """
    agent_id = event.get("agent_id", "")
    conversation_id = event.get("conversation_id", "")

    async with AsyncSessionLocal() as db:
        # Find the client that owns this agent
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.elevenlabs_agent_id == agent_id)
        )
        agent_config = result.scalar_one_or_none()

        if not agent_config:
            logger.warning(f"No client found for ElevenLabs agent {agent_id}")
            return

        client_id = agent_config.client_id

        # Fetch full conversation details from ElevenLabs
        try:
            conv_detail = await elevenlabs_service.get_conversation(conversation_id)
        except Exception as exc:
            logger.error(f"Failed to fetch conversation {conversation_id}: {exc}")
            conv_detail = event  # Fall back to webhook payload

        # Extract metadata
        metadata = conv_detail.get("metadata", {})
        transcript_data = conv_detail.get("transcript", [])
        analysis = conv_detail.get("analysis", {})

        start_time = metadata.get("start_time_unix_secs")
        duration = metadata.get("call_duration_secs")
        status_str = conv_detail.get("status", "done")

        # Determine channel and direction
        initiation = conv_detail.get("conversation_initiation_client_data", {})
        channel = _determine_channel(conv_detail)
        direction = conv_detail.get("direction", "inbound")

        # Determine caller number from conversation metadata
        caller_number = (
            metadata.get("phone_number")
            or metadata.get("caller_number")
            or initiation.get("phone_number", "")
            or "unknown"
        )

        # Look up phone_number_id if applicable
        phone_number_id = None
        if channel == "voice":
            pn_result = await db.execute(
                select(PhoneNumber.id).where(
                    PhoneNumber.client_id == client_id,
                    PhoneNumber.is_active == True,
                ).limit(1)
            )
            phone_number_id = pn_result.scalar_one_or_none()

        # Check if call already exists (idempotent)
        existing = await db.execute(
            select(Call).where(Call.elevenlabs_conversation_id == conversation_id)
        )
        call = existing.scalar_one_or_none()

        if not call:
            call = Call(
                client_id=client_id,
                phone_number_id=phone_number_id,
                caller_number=caller_number,
                direction=direction,
                channel=channel,
                status="completed",
                elevenlabs_conversation_id=conversation_id,
                started_at=datetime.fromtimestamp(start_time, tz=timezone.utc) if start_time else datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                duration_seconds=duration,
            )
            db.add(call)
            await db.flush()
            await db.refresh(call)
        else:
            call.status = "completed"
            call.ended_at = datetime.now(timezone.utc)
            if duration:
                call.duration_seconds = duration
            await db.flush()

        # Extract transcript turns
        turns = _extract_transcript_turns(transcript_data)

        # Build collected_data from analysis
        collected_data = {}
        if analysis:
            collected_data["call_successful"] = analysis.get("call_successful")
            collected_data["summary"] = analysis.get("transcript_summary")
            collected_data["data_collection"] = analysis.get("data_collection", {})
            collected_data["evaluation"] = analysis.get("evaluation_criteria_results", {})

        await db.commit()

        # Run post-call pipeline
        try:
            await PostCallService.process(
                db=db,
                call_id=call.id,
                turns=turns,
                collected_data=collected_data,
            )
        except Exception as exc:
            logger.error(f"Post-call pipeline failed for conv {conversation_id}: {exc}")


def _extract_transcript_turns(transcript_data: list[dict]) -> list[dict]:
    """Convert ElevenLabs transcript format to our standard format.

    ElevenLabs format: [{"role": "user"|"agent", "message": "...", "time_in_call_secs": 10}]
    Our format: [{"speaker": "agent"|"caller", "text": "...", "timestamp": 10.0}]
    """
    turns = []
    for entry in transcript_data:
        role = entry.get("role", "user")
        speaker = "agent" if role == "agent" else "caller"
        text = entry.get("message", "").strip()
        timestamp = entry.get("time_in_call_secs", 0.0)
        if text:
            turns.append({
                "speaker": speaker,
                "text": text,
                "timestamp": timestamp,
            })
    return turns


def _determine_channel(conv_detail: dict) -> str:
    """Determine if this was a voice call, text chat, or WhatsApp conversation."""
    source = conv_detail.get("conversation_initiation_source", "unknown")

    if source in ("phone_call", "twilio", "sip_trunk"):
        return "voice"
    elif source in ("widget", "web", "api"):
        return "text"
    elif source in ("whatsapp",):
        return "whatsapp"

    # Fallback: check if audio is present
    if conv_detail.get("has_audio") or conv_detail.get("has_user_audio"):
        return "voice"

    return "text"

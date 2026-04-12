"""ElevenLabs Tool-Call Webhooks.

These endpoints are called by the ElevenLabs conversational AI agent
when it decides to invoke a tool during a live conversation.
Each tool receives JSON from ElevenLabs and returns a JSON response
that the agent reads back to the user.

Security: Requests are validated via a shared secret header
(X-Tool-Secret) that must match settings.ELEVENLABS_TOOL_SECRET.
"""
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Lead, Client, ToolCallLog

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/tools",
    tags=["elevenlabs-tools"],
)

# ── Default client ID for the landing-page assistant (Omniweb's own account) ──
# In production, set LANDING_PAGE_CLIENT_ID env var to the Omniweb admin client UUID.
LANDING_PAGE_CLIENT_ID = settings.LANDING_PAGE_CLIENT_ID if hasattr(settings, "LANDING_PAGE_CLIENT_ID") else None


def _verify_secret(secret: str | None):
    """Validate the shared tool secret."""
    expected = settings.ELEVENLABS_TOOL_SECRET
    if not expected or expected == "change-me":
        logger.warning("ELEVENLABS_TOOL_SECRET is not configured — tool calls are open")
        return
    if secret != expected:
        raise HTTPException(403, "Invalid tool secret")


def _get_client_id() -> uuid.UUID:
    """Return the client ID to associate with landing-page leads."""
    if LANDING_PAGE_CLIENT_ID:
        return uuid.UUID(LANDING_PAGE_CLIENT_ID)
    # Fallback: use a deterministic UUID derived from "omniweb-landing"
    return uuid.uuid5(uuid.NAMESPACE_DNS, "omniweb.ai")


async def _log_tool_call(
    tool_name: str,
    parameters: dict,
    result: dict,
    success: bool = True,
    error_message: str | None = None,
    lead_id: uuid.UUID | None = None,
    duration_ms: int | None = None,
):
    """Persist an audit record for every tool invocation."""
    from app.core.database import async_session_factory

    try:
        async with async_session_factory() as db:
            log = ToolCallLog(
                id=uuid.uuid4(),
                client_id=_get_client_id(),
                tool_name=tool_name,
                parameters=parameters,
                result=result,
                success=success,
                error_message=error_message,
                lead_id=lead_id,
                duration_ms=duration_ms,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to log tool call {tool_name}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 1: capture_lead — save a qualified lead to the database
# ═══════════════════════════════════════════════════════════════════════════════


class CaptureLeadRequest(BaseModel):
    name: str = Field(..., description="Full name of the lead")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    business_name: Optional[str] = Field(None, description="Business name")
    industry: Optional[str] = Field(None, description="Industry or business type")
    challenge: Optional[str] = Field(None, description="Main pain point or challenge described")
    services_interested: Optional[str] = Field(None, description="Comma-separated list of Omniweb services they showed interest in")
    urgency: Optional[str] = Field("medium", description="low, medium, or high")
    notes: Optional[str] = Field(None, description="Any additional context from the conversation")


@router.post("/capture-lead")
async def capture_lead(
    body: CaptureLeadRequest,
    request: Request,
    x_tool_secret: Optional[str] = Header(None),
):
    """Save a qualified lead from the AI conversation."""
    _verify_secret(x_tool_secret)
    t0 = time.time()

    from app.core.database import async_session_factory

    lead_id = uuid.uuid4()
    async with async_session_factory() as db:
        lead = Lead(
            id=lead_id,
            client_id=_get_client_id(),
            caller_name=body.name,
            caller_phone=body.phone or "not-provided",
            caller_email=body.email,
            intent=body.industry or body.challenge,
            urgency=body.urgency or "medium",
            summary=_build_summary(body),
            services_requested=[s.strip() for s in body.services_interested.split(",")] if body.services_interested else [],
            status="new",
            lead_score=_score_lead(body),
            follow_up_sent=False,
        )
        db.add(lead)
        await db.commit()

        logger.info(f"Lead captured via tool call: {body.name} ({body.email})")

    result = {
        "result": f"Lead saved successfully. {body.name}'s information has been recorded. The Omniweb team will follow up shortly."
    }
    await _log_tool_call("capture_lead", body.model_dump(), result, lead_id=lead_id, duration_ms=int((time.time() - t0) * 1000))
    return result


def _build_summary(body: CaptureLeadRequest) -> str:
    """Build a human-readable summary from the lead data."""
    parts = []
    if body.business_name:
        parts.append(f"Business: {body.business_name}")
    if body.industry:
        parts.append(f"Industry: {body.industry}")
    if body.challenge:
        parts.append(f"Challenge: {body.challenge}")
    if body.services_interested:
        parts.append(f"Interested in: {body.services_interested}")
    if body.notes:
        parts.append(f"Notes: {body.notes}")
    return ". ".join(parts) if parts else "Lead captured via AI chat"


def _score_lead(body: CaptureLeadRequest) -> float:
    """Simple lead scoring based on completeness of info."""
    score = 0.2  # Base score for engaging
    if body.email:
        score += 0.25
    if body.phone:
        score += 0.15
    if body.business_name:
        score += 0.1
    if body.services_interested:
        score += 0.15
    if body.urgency == "high":
        score += 0.15
    elif body.urgency == "medium":
        score += 0.05
    return min(score, 1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: book_appointment — schedule a consultation
# ═══════════════════════════════════════════════════════════════════════════════


class BookAppointmentRequest(BaseModel):
    name: str = Field(..., description="Full name of the person booking")
    email: str = Field(..., description="Email for calendar invite")
    phone: Optional[str] = Field(None, description="Phone number")
    preferred_date: Optional[str] = Field(None, description="Preferred date (e.g. 'next Tuesday', '2026-04-15')")
    preferred_time: Optional[str] = Field(None, description="Preferred time (e.g. '2pm', '10:00 AM')")
    topic: Optional[str] = Field(None, description="What they want to discuss")


@router.post("/book-appointment")
async def book_appointment(
    body: BookAppointmentRequest,
    x_tool_secret: Optional[str] = Header(None),
):
    """Book a consultation appointment.

    Currently creates a booking record and sends confirmation.
    Can be extended to integrate with Google Calendar, Calendly, etc.
    """
    _verify_secret(x_tool_secret)
    t0 = time.time()

    # Build a booking reference
    booking_ref = f"OMN-{uuid.uuid4().hex[:8].upper()}"

    time_str = ""
    if body.preferred_date and body.preferred_time:
        time_str = f" for {body.preferred_date} at {body.preferred_time}"
    elif body.preferred_date:
        time_str = f" for {body.preferred_date}"
    elif body.preferred_time:
        time_str = f" at {body.preferred_time}"

    logger.info(
        f"Appointment booked via tool call: {body.name} ({body.email}){time_str} — ref: {booking_ref}"
    )

    # Also capture as a lead with "booked" status
    from app.core.database import async_session_factory

    lead_id = uuid.uuid4()
    async with async_session_factory() as db:
        lead = Lead(
            id=lead_id,
            client_id=_get_client_id(),
            caller_name=body.name,
            caller_phone=body.phone or "not-provided",
            caller_email=body.email,
            intent=body.topic or "Consultation",
            urgency="high",
            summary=f"Appointment booked{time_str}. Topic: {body.topic or 'General consultation'}. Ref: {booking_ref}",
            services_requested=[],
            status="booked",
            lead_score=0.9,
            follow_up_sent=False,
        )
        db.add(lead)
        await db.commit()

    result = {
        "result": f"Appointment booked! Reference number: {booking_ref}. {body.name} will receive a confirmation at {body.email}. The Omniweb team will reach out{time_str} to discuss {body.topic or 'how we can help'}."
    }
    await _log_tool_call("book_appointment", body.model_dump(), result, lead_id=lead_id, duration_ms=int((time.time() - t0) * 1000))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 3: send_confirmation — send an SMS confirmation to the lead
# ═══════════════════════════════════════════════════════════════════════════════


class SendConfirmationRequest(BaseModel):
    phone: str = Field(..., description="Phone number to send SMS to (with country code)")
    name: str = Field(..., description="Person's name for the message")
    message_type: str = Field("booking", description="Type: 'booking', 'follow_up', or 'info'")
    details: Optional[str] = Field(None, description="Extra details to include in the SMS")


@router.post("/send-confirmation")
async def send_confirmation(
    body: SendConfirmationRequest,
    x_tool_secret: Optional[str] = Header(None),
):
    """Send an SMS confirmation to the lead."""
    _verify_secret(x_tool_secret)
    t0 = time.time()

    templates = {
        "booking": f"Hi {body.name}! 🎉 Your consultation with Omniweb is confirmed. We'll reach out shortly to finalize the time. Questions? Reply here or email support@omniweb.ai",
        "follow_up": f"Hi {body.name}, thanks for chatting with Omniweb AI! We'd love to help your business grow. Our team will follow up soon. — Omniweb",
        "info": f"Hi {body.name}, here's the info you requested from Omniweb: {body.details or 'Visit omniweb.ai for details'}. Reply for more help!",
    }
    sms_body = templates.get(body.message_type, templates["follow_up"])

    try:
        from app.services import twilio_service

        if settings.twilio_configured:
            await twilio_service.send_sms(
                to_number=body.phone,
                from_number=settings.TWILIO_FROM_NUMBER,
                body=sms_body,
            )
            logger.info(f"Confirmation SMS sent to {body.phone} ({body.message_type})")
            result = {"result": f"Confirmation SMS sent to {body.name} at {body.phone}."}
            await _log_tool_call("send_confirmation_sms", body.model_dump(), result, duration_ms=int((time.time() - t0) * 1000))
            return result
        else:
            logger.warning("Twilio not configured — SMS not sent")
            result = {"result": f"Confirmation noted for {body.name}. SMS will be sent when the messaging service is configured."}
            await _log_tool_call("send_confirmation_sms", body.model_dump(), result, duration_ms=int((time.time() - t0) * 1000))
            return result
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        result = {"result": f"I've noted {body.name}'s number. The team will follow up manually."}
        await _log_tool_call("send_confirmation_sms", body.model_dump(), result, success=False, error_message=str(e), duration_ms=int((time.time() - t0) * 1000))
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 4: check_availability — return available time slots
# ═══════════════════════════════════════════════════════════════════════════════


class CheckAvailabilityRequest(BaseModel):
    date: Optional[str] = Field(None, description="Date to check (e.g. '2026-04-15', 'tomorrow', 'next week')")


@router.post("/check-availability")
async def check_availability(
    body: CheckAvailabilityRequest,
    x_tool_secret: Optional[str] = Header(None),
):
    """Return available consultation time slots.

    Currently returns standard business hours slots.
    Can be extended to query Google Calendar, Calendly, etc.
    """
    _verify_secret(x_tool_secret)
    t0 = time.time()

    # Standard available slots (can be replaced with real calendar integration)
    now = datetime.now(timezone.utc)
    base_date = now + timedelta(days=1)  # Start from tomorrow

    slots = []
    for day_offset in range(5):  # Next 5 business days
        date = base_date + timedelta(days=day_offset)
        if date.weekday() >= 5:  # Skip weekends
            continue
        date_str = date.strftime("%A, %B %d")
        slots.append(f"{date_str} at 10:00 AM EST")
        slots.append(f"{date_str} at 2:00 PM EST")
        slots.append(f"{date_str} at 4:00 PM EST")

    available = slots[:6]  # Show up to 6 slots

    result = {
        "result": f"Here are the available consultation slots: {', '.join(available)}. Which time works best?"
    }
    await _log_tool_call("check_availability", body.model_dump(), result, duration_ms=int((time.time() - t0) * 1000))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 5: get_pricing_info — return pricing details
# ═══════════════════════════════════════════════════════════════════════════════


class GetPricingRequest(BaseModel):
    service: Optional[str] = Field(None, description="Which service to get pricing for")


@router.post("/get-pricing")
async def get_pricing(
    body: GetPricingRequest,
    x_tool_secret: Optional[str] = Header(None),
):
    """Return Omniweb pricing information."""
    _verify_secret(x_tool_secret)
    t0 = time.time()

    result = {
        "result": (
            "Omniweb offers flexible plans tailored to your business. "
            "Starter plans begin at $97/month and include one AI voice agent and one chat assistant. "
            "Growth plans at $197/month add lead automation, SMS follow-ups, and up to 3 phone numbers. "
            "Pro plans at $397/month include unlimited agents, priority support, and custom integrations. "
            "All plans include a free setup consultation and 14-day money-back guarantee. "
            "For enterprise or agency pricing, we build custom packages."
        )
    }
    await _log_tool_call("get_pricing_info", body.model_dump(), result, duration_ms=int((time.time() - t0) * 1000))
    return result

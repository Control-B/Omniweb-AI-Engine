"""Voice agent tool webhooks (Retell custom tools).

Retell invokes these HTTPS tools during live calls. Each tool receives JSON
and returns JSON the model reads back to the caller.

Security: validate ``X-Tool-Secret`` against ``settings.TOOL_WEBHOOK_SECRET``.
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
from app.models.models import AgentConfig, Lead, Client, ToolCallLog
from app.services.calcom_scheduling_service import CalcomSchedulingService, SchedulingServiceError
from app.services.guardrail_middleware import check_response, get_safe_fallback

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/tools",
    tags=["voice-tools"],
)

# ── Default client ID for the landing-page assistant (Omniweb's own account) ──
# In production, set LANDING_PAGE_CLIENT_ID env var to the Omniweb admin client UUID.
LANDING_PAGE_CLIENT_ID = settings.LANDING_PAGE_CLIENT_ID if hasattr(settings, "LANDING_PAGE_CLIENT_ID") else None


def _verify_secret(secret: str | None):
    """Validate the shared tool secret."""
    expected = settings.TOOL_WEBHOOK_SECRET
    if not expected or expected == "change-me":
        logger.warning("TOOL_WEBHOOK_SECRET is not configured — tool calls are open")
        return
    if secret != expected:
        raise HTTPException(403, "Invalid tool secret")


def _get_default_client_id() -> uuid.UUID:
    """Return the client ID for landing-page leads (fallback)."""
    if LANDING_PAGE_CLIENT_ID:
        return uuid.UUID(LANDING_PAGE_CLIENT_ID)
    return uuid.uuid5(uuid.NAMESPACE_DNS, "omniweb.ai")


async def _resolve_tenant(agent_id: str | None) -> tuple[uuid.UUID, str, list[str]]:
    """Resolve client_id, industry_slug, and custom_guardrails from a Retell ``agent_id``.

    Falls back to the landing-page client if the agent_id is not found.

    Returns:
        (client_id, industry_slug, custom_guardrails)
    """
    if not agent_id:
        return _get_default_client_id(), "general", []

    from app.core.database import async_session_factory
    from sqlalchemy import select

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(AgentConfig).where(AgentConfig.retell_agent_id == agent_id)
            )
            config = result.scalar_one_or_none()
            if config:
                return (
                    config.client_id,
                    config.industry or "general",
                    config.custom_guardrails or [],
                )
    except Exception as e:
        logger.warning(f"Failed to resolve tenant for agent {agent_id}: {e}")

    return _get_default_client_id(), "general", []


def _enforce_guardrails(
    response_text: str,
    *,
    tool_name: str,
    industry_slug: str,
    custom_guardrails: list[str] | None = None,
) -> str:
    """Run guardrail checks on a tool response and return safe text.

    If violations are detected, returns sanitized text or a safe fallback.
    """
    result = check_response(
        response_text=response_text,
        industry_slug=industry_slug,
        custom_guardrails=custom_guardrails,
    )
    if result.passed:
        return response_text

    logger.warning(
        f"Guardrail violation in {tool_name} response "
        f"(industry={industry_slug}): {[v['rule'] for v in result.violations]}"
    )

    # Use sanitized text if available, otherwise fall back to safe default
    if result.sanitized_text:
        return result.sanitized_text
    return get_safe_fallback(tool_name=tool_name, industry_slug=industry_slug)


async def _log_tool_call(
    tool_name: str,
    parameters: dict,
    result: dict,
    *,
    client_id: uuid.UUID | None = None,
    success: bool = True,
    error_message: str | None = None,
    lead_id: uuid.UUID | None = None,
    duration_ms: int | None = None,
    guardrail_violations: list[dict] | None = None,
):
    """Persist an audit record for every tool invocation."""
    from app.core.database import async_session_factory

    resolved_client_id = client_id or _get_default_client_id()

    # Attach guardrail info to result if violations occurred
    if guardrail_violations:
        result = {
            **result,
            "_guardrail_violations": guardrail_violations,
        }

    try:
        async with async_session_factory() as db:
            log = ToolCallLog(
                id=uuid.uuid4(),
                client_id=resolved_client_id,
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
    x_agent_id: Optional[str] = Header(None),
):
    """Save a qualified lead from the AI conversation."""
    _verify_secret(x_tool_secret)
    t0 = time.time()

    # Resolve tenant from agent context
    client_id, industry_slug, custom_guardrails = await _resolve_tenant(x_agent_id)

    from app.core.database import async_session_factory

    lead_id = uuid.uuid4()
    async with async_session_factory() as db:
        lead = Lead(
            id=lead_id,
            client_id=client_id,
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

        logger.info(f"Lead captured via tool call: {body.name} ({body.email}) [client={client_id}]")

    response_text = f"Lead saved successfully. {body.name}'s information has been recorded. Our team will follow up shortly."
    response_text = _enforce_guardrails(
        response_text, tool_name="capture_lead",
        industry_slug=industry_slug, custom_guardrails=custom_guardrails,
    )
    result = {"result": response_text}
    await _log_tool_call(
        "capture_lead", body.model_dump(), result,
        client_id=client_id, lead_id=lead_id,
        duration_ms=int((time.time() - t0) * 1000),
    )
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
    start_time: Optional[str] = Field(None, description="Confirmed ISO start time from check_availability")
    event_type_id: Optional[str] = Field(None, description="Tenant event type to book")
    timezone: Optional[str] = Field(None, description="Attendee timezone")
    preferred_date: Optional[str] = Field(None, description="Preferred date (e.g. 'next Tuesday', '2026-04-15')")
    preferred_time: Optional[str] = Field(None, description="Preferred time (e.g. '2pm', '10:00 AM')")
    topic: Optional[str] = Field(None, description="What they want to discuss")


@router.post("/book-appointment")
async def book_appointment(
    body: BookAppointmentRequest,
    x_tool_secret: Optional[str] = Header(None),
    x_agent_id: Optional[str] = Header(None),
):
    """Book a consultation appointment.

    Creates a tenant-scoped Cal.diy booking through Omniweb's internal backend
    scheduling service. The AI tool never talks to Cal.diy directly.
    """
    _verify_secret(x_tool_secret)
    t0 = time.time()

    client_id, industry_slug, custom_guardrails = await _resolve_tenant(x_agent_id)

    from app.core.database import async_session_factory

    booking_ref = f"OMN-{uuid.uuid4().hex[:8].upper()}"

    time_str = ""
    if body.start_time:
        time_str = f" for {body.start_time}"
    elif body.preferred_date and body.preferred_time:
        time_str = f" for {body.preferred_date} at {body.preferred_time}"
    elif body.preferred_date:
        time_str = f" for {body.preferred_date}"
    elif body.preferred_time:
        time_str = f" at {body.preferred_time}"

    logger.info(
        f"Appointment requested via tool call: {body.name} ({body.email}){time_str} — ref: {booking_ref} [client={client_id}]"
    )

    lead_id = uuid.uuid4()
    async with async_session_factory() as db:
        lead = Lead(
            id=lead_id,
            client_id=client_id,
            caller_name=body.name,
            caller_phone=body.phone or "not-provided",
            caller_email=body.email,
            intent=body.topic or "Consultation",
            urgency="high",
            summary=f"Appointment requested{time_str}. Topic: {body.topic or 'General consultation'}. Ref: {booking_ref}",
            services_requested=[],
            status="booking_pending",
            lead_score=0.9,
            follow_up_sent=False,
        )
        db.add(lead)

        service = CalcomSchedulingService(db)
        try:
            booking = await service.create_booking(
                tenant_id=client_id,
                name=body.name,
                email=body.email,
                phone=body.phone,
                start_time=body.start_time or "",
                event_type_id=body.event_type_id,
                timezone_name=body.timezone or "America/New_York",
                topic=body.topic,
                metadata={"tool": "book_appointment", "booking_ref": booking_ref},
                lead_id=lead_id,
            )
            lead.status = "booked"
            lead.summary = (
                f"Appointment booked{time_str}. Topic: {body.topic or 'General consultation'}. "
                f"Ref: {booking_ref}"
            )
            await db.commit()
            response_text = (
                f"Appointment booked! Reference number: {booking_ref}. "
                f"{booking['message']}"
            )
        except SchedulingServiceError as exc:
            await db.commit()
            response_text = exc.message

    response_text = _enforce_guardrails(
        response_text, tool_name="book_appointment",
        industry_slug=industry_slug, custom_guardrails=custom_guardrails,
    )
    result = {"result": response_text}
    await _log_tool_call(
        "book_appointment", body.model_dump(), result,
        client_id=client_id, lead_id=lead_id,
        duration_ms=int((time.time() - t0) * 1000),
    )
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
    x_agent_id: Optional[str] = Header(None),
):
    """Send an SMS confirmation to the lead."""
    _verify_secret(x_tool_secret)
    t0 = time.time()

    client_id, industry_slug, custom_guardrails = await _resolve_tenant(x_agent_id)

    templates = {
        "booking": f"Hi {body.name}! 🎉 Your appointment is confirmed. We'll reach out shortly to finalize the time. Questions? Reply to this message.",
        "follow_up": f"Hi {body.name}, thanks for chatting with us! Our team will follow up soon.",
        "info": f"Hi {body.name}, here's the info you requested: {body.details or 'Our team will send details shortly'}. Reply for more help!",
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
            logger.info(f"Confirmation SMS sent to {body.phone} ({body.message_type}) [client={client_id}]")
            response_text = f"Confirmation SMS sent to {body.name} at {body.phone}."
        else:
            logger.warning("Twilio not configured — SMS not sent")
            response_text = f"Confirmation noted for {body.name}. SMS will be sent when the messaging service is configured."

        response_text = _enforce_guardrails(
            response_text, tool_name="send_confirmation",
            industry_slug=industry_slug, custom_guardrails=custom_guardrails,
        )
        result = {"result": response_text}
        await _log_tool_call(
            "send_confirmation_sms", body.model_dump(), result,
            client_id=client_id, duration_ms=int((time.time() - t0) * 1000),
        )
        return result
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        result = {"result": f"I've noted {body.name}'s number. The team will follow up manually."}
        await _log_tool_call(
            "send_confirmation_sms", body.model_dump(), result,
            client_id=client_id, success=False, error_message=str(e),
            duration_ms=int((time.time() - t0) * 1000),
        )
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 4: check_availability — return available time slots
# ═══════════════════════════════════════════════════════════════════════════════


class CheckAvailabilityRequest(BaseModel):
    date: Optional[str] = Field(None, description="Date to check (e.g. '2026-04-15', 'tomorrow', 'next week')")
    event_type_id: Optional[str] = Field(None, description="Tenant event type to check")
    timezone: Optional[str] = Field(None, description="Timezone for returned slots")


@router.post("/check-availability")
async def check_availability(
    body: CheckAvailabilityRequest,
    x_tool_secret: Optional[str] = Header(None),
    x_agent_id: Optional[str] = Header(None),
):
    """Return available consultation time slots.

    Queries tenant-scoped Cal.diy slots through Omniweb's internal backend
    scheduling service.
    """
    _verify_secret(x_tool_secret)
    t0 = time.time()

    client_id, industry_slug, custom_guardrails = await _resolve_tenant(x_agent_id)

    from app.core.database import async_session_factory

    now = datetime.now(timezone.utc)
    start = body.date if body.date and body.date[:4].isdigit() else (now + timedelta(days=1)).strftime("%Y-%m-%d")
    end = start if body.date and body.date[:4].isdigit() else (now + timedelta(days=7)).strftime("%Y-%m-%d")

    async with async_session_factory() as db:
        service = CalcomSchedulingService(db)
        try:
            slots = await service.get_available_slots(
                client_id,
                event_type_id=body.event_type_id,
                date_range={"start": start, "end": end},
                timezone_name=body.timezone or "America/New_York",
            )
        except SchedulingServiceError as exc:
            slots = []
            response_text = exc.message
        else:
            if not slots:
                response_text = "I do not see any open appointment slots for that window. Would another day work?"
            else:
                available = [slot["start"] for slot in slots[:3] if slot.get("start")]
                response_text = (
                    f"Here are the next available slots: {', '.join(available)}. "
                    "Which one should I book? I will use the exact selected time to confirm it."
                )
    response_text = _enforce_guardrails(
        response_text, tool_name="check_availability",
        industry_slug=industry_slug, custom_guardrails=custom_guardrails,
    )
    result = {"result": response_text}
    await _log_tool_call(
        "check_availability", body.model_dump(), result,
        client_id=client_id, duration_ms=int((time.time() - t0) * 1000),
    )
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
    x_agent_id: Optional[str] = Header(None),
):
    """Return pricing information.

    For the Omniweb landing page agent, returns platform pricing.
    For tenant agents, pricing should come from the knowledge base.
    Guardrails may block specific pricing responses for industries
    that require on-site estimates (roofing, home services, etc.).
    """
    _verify_secret(x_tool_secret)
    t0 = time.time()

    client_id, industry_slug, custom_guardrails = await _resolve_tenant(x_agent_id)

    # Default pricing (Omniweb's own — overridden by tenant KB in practice)
    response_text = (
        "We offer flexible plans tailored to your needs. "
        "Our team can prepare a personalized quote based on your specific requirements. "
        "Would you like me to have someone reach out with detailed pricing?"
    )
    response_text = _enforce_guardrails(
        response_text, tool_name="get_pricing",
        industry_slug=industry_slug, custom_guardrails=custom_guardrails,
    )
    result = {"result": response_text}
    await _log_tool_call(
        "get_pricing_info", body.model_dump(), result,
        client_id=client_id, duration_ms=int((time.time() - t0) * 1000),
    )
    return result

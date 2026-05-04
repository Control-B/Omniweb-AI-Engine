"""Assistant appointment scheduling workflow.

This is intentionally booking-link first: Cal.com DIY credentials never leave
the backend, and v1 only returns an approved booking URL for the visitor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import AgentConfig, AppointmentRequest, Client, EmailLog, Lead, TenantSchedulingConfig
from app.services import email_service

settings = get_settings()

SCHEDULING_INTENT_KEYWORDS = (
    "book appointment",
    "book an appointment",
    "schedule appointment",
    "schedule consultation",
    "set up a demo",
    "setup a demo",
    "book a demo",
    "call me",
    "contact me",
    "someone contact me",
    "i need service",
    "need service",
    "appointment",
    "consultation",
    "schedule",
)

EMAIL_REQUEST_INTENT_KEYWORDS = (
    "contact me",
    "contact us",
    "reach me",
    "reach out",
    "follow up",
    "get back to me",
    "email me",
    "send me an email",
    "send an email",
    "send email",
    "email the details",
    "send me the details",
    "send me details",
    "send me more information",
    "send me information",
    "send info",
    "send it to my email",
    "send this to my email",
)

TRUSTED_BOOKING_DOMAINS = {
    "cal.com",
    "www.cal.com",
    "cal.dev",
    "www.cal.dev",
}


@dataclass
class SchedulePayload:
    tenant_id: UUID
    conversation_id: str
    visitor_name: str
    visitor_email: str
    visitor_phone: str | None = None
    requested_service: str | None = None
    preferred_date: str | None = None
    preferred_time: str | None = None
    notes: str | None = None
    source_url: str | None = None


@dataclass
class EmailRequestPayload:
    tenant_id: UUID
    conversation_id: str
    visitor_email: str
    visitor_name: str | None = None
    visitor_phone: str | None = None
    notes: str | None = None
    source_url: str | None = None


def has_scheduling_intent(text: str) -> bool:
    normalized = (text or "").lower()
    return any(keyword in normalized for keyword in SCHEDULING_INTENT_KEYWORDS)


def has_email_request_intent(text: str) -> bool:
    normalized = (text or "").lower()
    return any(keyword in normalized for keyword in EMAIL_REQUEST_INTENT_KEYWORDS)


def build_email_request_payload_from_text(
    *,
    tenant_id: UUID,
    conversation_id: str,
    text: str,
    source_url: str | None = None,
) -> EmailRequestPayload | None:
    if not has_email_request_intent(text):
        return None
    visitor_email = extract_email(text)
    if not visitor_email:
        return None
    return EmailRequestPayload(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        visitor_email=visitor_email,
        visitor_name=extract_name(text),
        visitor_phone=extract_phone(text),
        notes=text[:4000],
        source_url=source_url,
    )


def extract_email(text: str) -> str | None:
    match = re.search(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}", text or "")
    return match.group(0).strip(".,;:()[]") if match else None


def extract_phone(text: str) -> str | None:
    match = re.search(r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)", text or "")
    return match.group(0).strip() if match else None


def extract_name(text: str) -> str | None:
    patterns = [
        r"(?:my name is|i am|i'm|this is)\s+([A-Za-z][A-Za-z' -]{1,80})",
        r"(?:name[:\s]+)([A-Za-z][A-Za-z' -]{1,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if match:
            value = re.split(r"\s+(?:and|email|phone|number|service)\b", match.group(1).strip(), maxsplit=1, flags=re.IGNORECASE)[0]
            return value.strip(" .,!")[:120] or None
    return None


def merge_schedule_state(existing: dict[str, Any] | None, message: str, *, source_url: str | None = None) -> dict[str, Any]:
    state = dict(existing or {})
    if email := extract_email(message):
        state["visitorEmail"] = email
    if phone := extract_phone(message):
        state["visitorPhone"] = phone
    if name := extract_name(message):
        state["visitorName"] = name
    if source_url:
        state["sourceUrl"] = source_url
    # Preserve a useful free-form note for the business. The LLM can still ask
    # clarifying questions, but this keeps the raw visitor request attached to
    # the appointment request.
    notes = [str(item) for item in state.get("notesHistory", []) if item]
    if message.strip():
        notes.append(message.strip()[:1000])
    state["notesHistory"] = notes[-5:]
    if not state.get("notes") and notes:
        state["notes"] = "\n".join(notes[-3:])
    return state


def merge_email_request_state(existing: dict[str, Any] | None, message: str, *, source_url: str | None = None) -> dict[str, Any]:
    state = dict(existing or {})
    if email := extract_email(message):
        state["visitorEmail"] = email
    if phone := extract_phone(message):
        state["visitorPhone"] = phone
    if name := extract_name(message):
        state["visitorName"] = name
    if source_url:
        state["sourceUrl"] = source_url
    notes = [str(item) for item in state.get("notesHistory", []) if item]
    if message.strip():
        notes.append(message.strip()[:1000])
    state["notesHistory"] = notes[-5:]
    state["notes"] = "\n".join(notes[-3:])
    return state


def missing_email_request_fields(state: dict[str, Any]) -> list[str]:
    return [] if (state.get("visitorEmail") or "").strip() else ["email"]


def missing_email_fields_prompt(*, language: str | None = None) -> str:
    lang = (language or "").strip().lower().split("-", 1)[0]
    localized = {
        "es": "Claro. ¿A qué correo debo enviarlo?",
        "fr": "Bien sûr. À quelle adresse e-mail dois-je l'envoyer ?",
        "de": "Gerne. An welche E-Mail-Adresse soll ich es senden?",
        "pt": "Claro. Para qual e-mail devo enviar?",
        "it": "Certo. A quale indirizzo email devo inviarlo?",
    }
    return localized.get(lang, "Absolutely. What email address should I send it to?")


def missing_schedule_fields(state: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not (state.get("visitorName") or "").strip():
        missing.append("name")
    if not (state.get("visitorEmail") or "").strip():
        missing.append("email")
    return missing


def missing_fields_prompt(missing: list[str], *, language: str | None = None) -> str:
    # Keep this conservative: ask only for required missing fields and avoid
    # forcing English when the broader assistant is in auto-language mode.
    lang = (language or "").strip().lower().split("-", 1)[0]
    localized = {
        "es": {
            "name": "Puedo ayudarte a reservar eso. ¿Qué nombre debo poner en la solicitud?",
            "email": "Puedo ayudarte a reservar eso. ¿Qué correo debemos usar para la confirmación?",
            "both": "Puedo ayudarte a reservar eso. ¿Qué nombre y correo debemos usar para la solicitud?",
        },
        "fr": {
            "name": "Je peux vous aider à réserver. Quel nom dois-je indiquer sur la demande ?",
            "email": "Je peux vous aider à réserver. Quelle adresse e-mail devons-nous utiliser pour la confirmation ?",
            "both": "Je peux vous aider à réserver. Quel nom et quelle adresse e-mail devons-nous utiliser ?",
        },
        "de": {
            "name": "Ich kann Ihnen beim Buchen helfen. Welchen Namen soll ich für die Anfrage verwenden?",
            "email": "Ich kann Ihnen beim Buchen helfen. Welche E-Mail-Adresse sollen wir für die Bestätigung verwenden?",
            "both": "Ich kann Ihnen beim Buchen helfen. Welchen Namen und welche E-Mail-Adresse sollen wir verwenden?",
        },
        "pt": {
            "name": "Posso ajudar você a agendar. Que nome devo colocar na solicitação?",
            "email": "Posso ajudar você a agendar. Qual e-mail devemos usar para a confirmação?",
            "both": "Posso ajudar você a agendar. Que nome e e-mail devemos usar para a solicitação?",
        },
        "it": {
            "name": "Posso aiutarti a prenotare. Che nome devo inserire nella richiesta?",
            "email": "Posso aiutarti a prenotare. Quale email dobbiamo usare per la conferma?",
            "both": "Posso aiutarti a prenotare. Che nome ed email dobbiamo usare per la richiesta?",
        },
    }.get(lang)
    key = "name" if missing == ["name"] else "email" if missing == ["email"] else "both"
    if localized:
        return localized[key]
    if missing == ["name"]:
        return "I can help you book that. What name should I put on the request?"
    if missing == ["email"]:
        return "I can help you book that. What email should we use for the confirmation?"
    return "I can help you book that. What name and email should we use for the appointment request?"


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\r\n]+", " ", str(value)).strip()
    return cleaned[:limit] or None


def _is_safe_booking_url(url: str, *, tenant_allowed: bool = False) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return False
    if tenant_allowed:
        return True
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if host in TRUSTED_BOOKING_DOMAINS or host.endswith(".cal.com") or host.endswith(".cal.dev"):
        return True
    configured_base = (settings.CALCOM_BASE_URL or "").strip()
    if configured_base:
        try:
            return host == urlparse(configured_base).netloc.lower().split(":")[0]
        except Exception:
            return False
    return False


async def resolve_booking_url(db: AsyncSession, client: Client, agent: AgentConfig | None) -> str:
    result = await db.execute(
        select(TenantSchedulingConfig).where(TenantSchedulingConfig.tenant_id == client.id)
    )
    scheduling_config = result.scalar_one_or_none()
    configured = ""
    if scheduling_config and isinstance(scheduling_config.settings_json, dict):
        configured = str(scheduling_config.settings_json.get("bookingUrl") or scheduling_config.settings_json.get("booking_url") or "").strip()
    if not configured and agent and agent.booking_url:
        configured = agent.booking_url.strip()
    if configured:
        if not _is_safe_booking_url(configured, tenant_allowed=True):
            raise ValueError("Tenant booking URL is not valid")
        return configured

    fallback = (settings.CALCOM_BOOKING_URL or "").strip()
    if fallback:
        if not _is_safe_booking_url(fallback):
            raise ValueError("Default Cal.com booking URL is not allowed")
        return fallback

    base = (settings.CALCOM_BASE_URL or "https://cal.com").rstrip("/")
    event_type_id = (
        (scheduling_config.default_event_type_id if scheduling_config else None)
        or settings.CALCOM_EVENT_TYPE_ID
        or settings.CALCOM_DEFAULT_EVENT_TYPE_ID
        or ""
    )
    if event_type_id:
        return f"{base}/event-types/{event_type_id}"
    raise ValueError("No Cal.com booking URL configured")


async def create_schedule_request(
    db: AsyncSession,
    payload: SchedulePayload,
) -> tuple[AppointmentRequest, Client, AgentConfig | None, bool]:
    client = await db.get(Client, payload.tenant_id)
    if not client:
        raise ValueError("Tenant not found")
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client.id))
    agent = result.scalar_one_or_none()

    visitor_name = _clean(payload.visitor_name, 255)
    visitor_email = _clean(payload.visitor_email, 255)
    if not visitor_name:
        raise ValueError("visitorName is required")
    if not visitor_email or "@" not in visitor_email:
        raise ValueError("visitorEmail is required")

    existing_result = await db.execute(
        select(AppointmentRequest).where(
            AppointmentRequest.tenant_id == client.id,
            AppointmentRequest.conversation_id == payload.conversation_id[:120],
            AppointmentRequest.visitor_email == visitor_email.lower(),
            AppointmentRequest.status.in_(["pending", "link_sent"]),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return existing, client, agent, True

    booking_url = await resolve_booking_url(db, client, agent)
    request = AppointmentRequest(
        tenant_id=client.id,
        conversation_id=payload.conversation_id[:120],
        visitor_name=visitor_name,
        visitor_email=visitor_email.lower(),
        visitor_phone=_clean(payload.visitor_phone, 30),
        requested_service=_clean(payload.requested_service, 255),
        preferred_date=_clean(payload.preferred_date, 80),
        preferred_time=_clean(payload.preferred_time, 80),
        notes=_clean(payload.notes, 4000),
        booking_url=booking_url,
        source_url=_clean(payload.source_url, 2048),
        status="link_sent",
        metadata_json={"source": "assistant_schedule"},
    )
    db.add(request)

    # Save a lightweight lead for the revenue pipeline.
    lead = Lead(
        client_id=client.id,
        caller_name=visitor_name,
        caller_email=visitor_email.lower(),
        caller_phone=_clean(payload.visitor_phone, 30) or "",
        intent="schedule_appointment",
        urgency="medium",
        summary=_clean(payload.notes, 1000),
        services_requested=[payload.requested_service] if payload.requested_service else [],
        status="new",
        lead_score=0.8,
    )
    db.add(lead)
    await db.flush()
    return request, client, agent, False


async def send_schedule_emails(
    db: AsyncSession,
    *,
    appointment: AppointmentRequest,
    client: Client,
    agent: AgentConfig | None,
) -> dict[str, bool]:
    business_name = (agent.business_name if agent and agent.business_name else client.name) or "the business"
    result = await db.execute(
        select(TenantSchedulingConfig).where(TenantSchedulingConfig.tenant_id == client.id)
    )
    scheduling_config = result.scalar_one_or_none()
    scheduling_settings = (
        scheduling_config.settings_json
        if scheduling_config and isinstance(scheduling_config.settings_json, dict)
        else {}
    )
    notify_to = (
        str(scheduling_settings.get("notificationEmail") or "").strip()
        or (client.notification_email or "").strip()
        or (agent.handoff_email if agent else "")
        or client.email
    )
    from_email = str(scheduling_settings.get("resendFromEmail") or "").strip() or None
    tenant_reply_to_email = (
        str(scheduling_settings.get("resendReplyToEmail") or "").strip()
        or notify_to
    )
    details = {
        "business_name": business_name,
        "visitor_name": appointment.visitor_name,
        "visitor_email": appointment.visitor_email,
        "visitor_phone": appointment.visitor_phone,
        "requested_service": appointment.requested_service,
        "preferred_date": appointment.preferred_date,
        "preferred_time": appointment.preferred_time,
        "notes": appointment.notes,
        "source_url": appointment.source_url,
        "booking_url": appointment.booking_url,
    }
    visitor_ok = await email_service.sendVisitorConfirmationEmail(
        db,
        tenant_id=client.id,
        conversation_id=appointment.conversation_id,
        to=appointment.visitor_email,
        from_email=from_email,
        reply_to_email=tenant_reply_to_email,
        **details,
    )
    owner_ok = await email_service.sendAppointmentRequestEmail(
        db,
        tenant_id=client.id,
        conversation_id=appointment.conversation_id,
        to=notify_to,
        from_email=from_email,
        reply_to_email=appointment.visitor_email,
        **details,
    )
    return {"visitorConfirmation": visitor_ok, "businessNotification": owner_ok}


async def send_requested_email(
    db: AsyncSession,
    payload: EmailRequestPayload,
) -> dict[str, bool]:
    client = await db.get(Client, payload.tenant_id)
    if not client:
        raise ValueError("Tenant not found")
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client.id))
    agent = result.scalar_one_or_none()

    visitor_email = _clean(payload.visitor_email, 255)
    if not visitor_email or "@" not in visitor_email:
        raise ValueError("visitorEmail is required")
    visitor_email = visitor_email.lower()

    existing_result = await db.execute(
        select(EmailLog).where(
            EmailLog.tenant_id == client.id,
            EmailLog.conversation_id == payload.conversation_id[:120],
            EmailLog.recipient == visitor_email,
            EmailLog.type == "visitor_requested_email",
            EmailLog.status == "sent",
        )
    )
    if existing_result.scalar_one_or_none():
        return {"visitorEmail": True, "businessNotification": True}

    scheduling_result = await db.execute(
        select(TenantSchedulingConfig).where(TenantSchedulingConfig.tenant_id == client.id)
    )
    scheduling_config = scheduling_result.scalar_one_or_none()
    scheduling_settings = (
        scheduling_config.settings_json
        if scheduling_config and isinstance(scheduling_config.settings_json, dict)
        else {}
    )
    notify_to = (
        str(scheduling_settings.get("notificationEmail") or "").strip()
        or (client.notification_email or "").strip()
        or (agent.handoff_email if agent else "")
        or client.email
    )
    from_email = str(scheduling_settings.get("resendFromEmail") or "").strip() or None
    tenant_reply_to_email = (
        str(scheduling_settings.get("resendReplyToEmail") or "").strip()
        or notify_to
    )
    business_name = (agent.business_name if agent and agent.business_name else client.name) or "the business"
    visitor_name = _clean(payload.visitor_name, 255) or "Website visitor"
    details = {
        "business_name": business_name,
        "visitor_name": visitor_name,
        "visitor_email": visitor_email,
        "visitor_phone": _clean(payload.visitor_phone, 30),
        "notes": _clean(payload.notes, 4000),
        "source_url": _clean(payload.source_url, 2048),
    }

    visitor_ok = await email_service.sendVisitorRequestedEmail(
        db,
        tenant_id=client.id,
        conversation_id=payload.conversation_id[:120],
        to=visitor_email,
        from_email=from_email,
        reply_to_email=tenant_reply_to_email,
        **details,
    )
    owner_ok = await email_service.sendLeadNotificationEmail(
        db,
        tenant_id=client.id,
        conversation_id=payload.conversation_id[:120],
        to=notify_to,
        from_email=from_email,
        reply_to_email=visitor_email,
        **details,
    )
    return {"visitorEmail": visitor_ok, "businessNotification": owner_ok}

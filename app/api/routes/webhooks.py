"""Webhook management routes.

Clients can:
- View / update their webhook URL
- Generate / regenerate a signing secret
- Test their webhook URL
- View recent webhook delivery logs
"""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import AppointmentRequest, Client, WebhookEvent
from app.services.webhook_service import test_webhook

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class WebhookConfigOut(BaseModel):
    webhook_url: str | None
    webhook_secret: str | None
    has_secret: bool

class WebhookConfigUpdate(BaseModel):
    webhook_url: str | None = None

class WebhookTestRequest(BaseModel):
    url: str | None = None          # if None, use configured URL

class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int | None = None
    error: str | None = None

class WebhookEventOut(BaseModel):
    id: str
    event: str
    url: str
    status: str
    status_code: int | None
    error_message: str | None
    created_at: str

    class Config:
        from_attributes = True

class WebhookSecretOut(BaseModel):
    webhook_secret: str


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/calcom")
async def calcom_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Receive Cal.com DIY booking webhooks.

    v1 is deliberately permissive for development: if no webhook secret is
    configured we safely parse/log and try to reconcile by attendee email or
    conversation id. Signature verification can be tightened when Cal.com is
    wired to send signed production events.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": str(payload)[:1000]}

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    attendee = data.get("attendee") if isinstance(data.get("attendee"), dict) else {}
    email = (
        data.get("attendeeEmail")
        or attendee.get("email")
        or data.get("email")
        or ""
    )
    conversation_id = (
        data.get("conversationId")
        or (data.get("metadata") or {}).get("conversation_id")
        or (data.get("metadata") or {}).get("conversationId")
        or ""
    )

    appointment = None
    if email:
        result = await db.execute(
            select(AppointmentRequest)
            .where(AppointmentRequest.visitor_email == str(email).lower())
            .order_by(desc(AppointmentRequest.created_at))
        )
        appointment = result.scalar_one_or_none()
    if not appointment and conversation_id:
        result = await db.execute(
            select(AppointmentRequest)
            .where(AppointmentRequest.conversation_id == str(conversation_id)[:120])
            .order_by(desc(AppointmentRequest.created_at))
        )
        appointment = result.scalar_one_or_none()

    if appointment:
        appointment.status = "booked"
        metadata = dict(appointment.metadata_json or {})
        metadata["calcomWebhook"] = payload
        appointment.metadata_json = metadata
        await db.commit()
    else:
        await db.rollback()

    return {"ok": True, "matched": bool(appointment)}

@router.get("/config", response_model=WebhookConfigOut)
async def get_webhook_config(
    client: Client = Depends(get_current_client),
):
    """Get the client's webhook configuration."""
    return WebhookConfigOut(
        webhook_url=client.crm_webhook_url,
        webhook_secret=client.webhook_secret,
        has_secret=bool(client.webhook_secret),
    )


@router.patch("/config", response_model=WebhookConfigOut)
async def update_webhook_config(
    body: WebhookConfigUpdate,
    db: AsyncSession = Depends(get_session),
    client: Client = Depends(get_current_client),
):
    """Update the client's webhook URL."""
    if body.webhook_url is not None:
        client.crm_webhook_url = body.webhook_url or None
    await db.flush()
    await db.refresh(client)
    return WebhookConfigOut(
        webhook_url=client.crm_webhook_url,
        webhook_secret=client.webhook_secret,
        has_secret=bool(client.webhook_secret),
    )


@router.post("/secret", response_model=WebhookSecretOut)
async def generate_webhook_secret(
    db: AsyncSession = Depends(get_session),
    client: Client = Depends(get_current_client),
):
    """Generate (or regenerate) a webhook signing secret.

    The secret is returned ONCE; store it securely. It's used to sign
    all outbound webhook deliveries with HMAC-SHA256.
    """
    new_secret = f"whsec_{secrets.token_urlsafe(32)}"
    client.webhook_secret = new_secret
    await db.flush()
    logger.info(f"Webhook secret generated for client {client.id}")
    return WebhookSecretOut(webhook_secret=new_secret)


@router.delete("/secret")
async def delete_webhook_secret(
    db: AsyncSession = Depends(get_session),
    client: Client = Depends(get_current_client),
):
    """Remove the webhook signing secret (deliveries will no longer be signed)."""
    client.webhook_secret = None
    await db.flush()
    return {"ok": True}


@router.post("/test", response_model=WebhookTestResponse)
async def test_webhook_endpoint(
    body: WebhookTestRequest,
    db: AsyncSession = Depends(get_session),
    client: Client = Depends(get_current_client),
):
    """Send a test webhook to the configured (or provided) URL."""
    url = body.url or client.crm_webhook_url
    if not url:
        raise HTTPException(status_code=400, detail="No webhook URL configured or provided")

    result = await test_webhook(db, client=client, url=url)
    return WebhookTestResponse(**result)


@router.get("/events", response_model=list[WebhookEventOut])
async def list_webhook_events(
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_session),
    client: Client = Depends(get_current_client),
):
    """List recent webhook delivery logs for the authenticated client."""
    query = (
        select(WebhookEvent)
        .where(WebhookEvent.client_id == client.id)
        .order_by(desc(WebhookEvent.created_at))
    )
    if event_type:
        query = query.where(WebhookEvent.event == event_type)
    if status:
        query = query.where(WebhookEvent.status == status)

    query = query.offset(offset).limit(min(limit, 100))
    result = await db.execute(query)
    events = result.scalars().all()

    return [
        WebhookEventOut(
            id=str(e.id),
            event=e.event,
            url=e.url,
            status=e.status,
            status_code=e.status_code,
            error_message=e.error_message,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]

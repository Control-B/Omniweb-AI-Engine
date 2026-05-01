"""Subscription API — Stripe Checkout Sessions & subscription management.

Endpoints:
    POST /subscribe/checkout    — create a Stripe Checkout session
    POST /subscribe/portal      — create a Stripe Billing Portal session
    GET  /subscribe/status       — get current subscription status
"""
import stripe
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Client

logger = get_logger(__name__)
router = APIRouter(prefix="/subscribe", tags=["subscribe"])
settings = get_settings()


# Map plan names to Stripe price IDs (configure via env vars)
PLAN_PRICE_MAP = {
    "starter": getattr(settings, "STRIPE_PRICE_STARTER", "price_starter"),
    "growth": getattr(settings, "STRIPE_PRICE_GROWTH", "price_growth"),
    "pro": getattr(settings, "STRIPE_PRICE_PRO", "price_pro"),
}


class CheckoutRequest(BaseModel):
    plan: str  # starter, growth, pro
    success_url: str | None = None
    cancel_url: str | None = None


class PortalRequest(BaseModel):
    return_url: str | None = None


@router.post("/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a Stripe Checkout session for the client to subscribe."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe is not configured")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    price_id = PLAN_PRICE_MAP.get(body.plan)
    if not price_id:
        raise HTTPException(400, f"Unknown plan: {body.plan}")

    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    base = settings.PLATFORM_URL.rstrip("/")
    success_url = body.success_url or f"{base}/dashboard?subscribed=true"
    cancel_url = body.cancel_url or f"{base}/pricing"

    # Create or reuse Stripe customer
    if not client.stripe_customer_id:
        customer = stripe.Customer.create(
            email=client.email,
            name=client.name,
            metadata={"client_id": str(client.id)},
        )
        client.stripe_customer_id = customer.id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=client.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"client_id": str(client.id), "plan": body.plan},
        subscription_data={
            "metadata": {"client_id": str(client.id), "plan": body.plan},
        },
    )

    logger.info(f"Checkout session created for {client.email}: {session.id}")

    return {
        "checkout_url": session.url,
        "session_id": session.id,
    }


@router.post("/portal")
async def create_billing_portal(
    body: PortalRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a Stripe Billing Portal session for managing subscription."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe is not configured")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    client = await db.get(Client, current_client["client_id"])
    if not client or not client.stripe_customer_id:
        raise HTTPException(404, "No billing account found. Subscribe first.")

    return_url = body.return_url or f"{settings.PLATFORM_URL.rstrip('/')}/dashboard"

    session = stripe.billing_portal.Session.create(
        customer=client.stripe_customer_id,
        return_url=return_url,
    )

    return {"portal_url": session.url}


@router.get("/status")
async def get_subscription_status(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the client's current subscription status."""
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    now = datetime.now(timezone.utc)

    # Determine subscription state
    if client.stripe_subscription_id:
        status = "active"
    elif client.trial_ends_at and client.trial_ends_at > now:
        status = "trial"
    elif client.trial_ends_at and client.trial_ends_at <= now:
        status = "trial_expired"
    else:
        status = "none"

    return {
        "status": status,
        "plan": client.plan,
        "trial_ends_at": client.trial_ends_at.isoformat() if client.trial_ends_at else None,
        "stripe_subscription_id": client.stripe_subscription_id,
        "is_active": client.is_active,
        "minutes_used": client.plan_minutes_used,
    }

"""Stripe webhook handler — subscription lifecycle events."""
import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Client

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks"])

PLAN_MAP = {
    # price_id → plan enum value
    # Update these with your actual Stripe price IDs
    "price_starter": "starter",
    "price_growth": "growth",
    "price_pro": "pro",
    "price_agency": "agency",
}


@router.post("")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        event = stripe.Event.construct_from(
            {"type": "test", "data": {}}, stripe.api_key
        )
        return {"ok": True, "note": "stripe not configured"}

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_type = event["type"]
    data = event["data"]["object"]
    logger.info(f"Stripe webhook: {event_type}")

    async with get_session() as db:
        if event_type == "customer.subscription.created":
            await _update_subscription(db, data, active=True)
        elif event_type == "customer.subscription.updated":
            await _update_subscription(db, data, active=True)
        elif event_type == "customer.subscription.deleted":
            await _update_subscription(db, data, active=False)
        elif event_type == "invoice.payment_failed":
            logger.warning(f"Payment failed for customer: {data.get('customer')}")

    return {"ok": True}


async def _update_subscription(db: AsyncSession, subscription: dict, active: bool) -> None:
    customer_id = subscription.get("customer")
    result = await db.execute(
        select(Client).where(Client.stripe_customer_id == customer_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        logger.warning(f"No client found for Stripe customer: {customer_id}")
        return

    client.stripe_subscription_id = subscription.get("id")
    client.is_active = active

    # Manage embed code expiry based on subscription status
    if active:
        # Active subscription — embed code never expires
        client.embed_expires_at = None
    else:
        # Subscription cancelled — expire embed code immediately
        from datetime import datetime, timezone
        client.embed_expires_at = datetime.now(timezone.utc)

    # Determine plan from price ID
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        if price_id in PLAN_MAP:
            client.plan = PLAN_MAP[price_id]

    await db.commit()
    logger.info(f"Updated client {client.id} subscription: active={active} plan={client.plan}")

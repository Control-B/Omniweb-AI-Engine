"""Omniweb Agent Engine — FastAPI application.

This is the DATA PLANE. It:
  - Manages multi-tenant client accounts and auth
  - Creates/syncs ElevenLabs agents per client
  - Receives ElevenLabs post-conversation webhooks
  - Serves call history, transcripts, leads to the dashboard
  - Handles Stripe billing webhooks
  - Manages phone numbers (buy via Twilio, import into ElevenLabs)
  - Sends SMS via Twilio
  - Provides text chat widget configuration

All real-time voice/text AI is hosted by ElevenLabs.
No agent worker process needed.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging, get_logger

# Import all route modules
from app.api.routes import (
    admin,
    agent_config,
    analytics,
    auth,
    automations,
    calls,
    chat,
    embed,
    industry,
    knowledge_base,
    leads,
    numbers,
    subscribe,
    templates,
    webhooks,
    webhooks_elevenlabs,
    webhooks_stripe,
    webhooks_tools,
)

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


import asyncio as _asyncio


async def _scheduled_tasks():
    """Background loop that runs periodic maintenance tasks.

    - Trial expiry emails (3 days + 1 day warnings)
    - Monthly plan_minutes_used reset (1st of each month)
    Runs every 6 hours.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, and_, update
    from app.core.database import AsyncSessionLocal
    from app.models.models import Client
    from app.services.email_service import send_trial_expiring_email

    while True:
        try:
            await _asyncio.sleep(6 * 3600)  # every 6 hours
            now = datetime.now(timezone.utc)

            async with AsyncSessionLocal() as db:
                # ── Trial expiry warnings ──
                for days_ahead in [3, 1]:
                    window_start = now + timedelta(days=days_ahead - 0.25)
                    window_end = now + timedelta(days=days_ahead + 0.25)
                    result = await db.execute(
                        select(Client).where(
                            and_(
                                Client.trial_ends_at >= window_start,
                                Client.trial_ends_at < window_end,
                                Client.stripe_subscription_id.is_(None),
                                Client.is_active == True,
                            )
                        )
                    )
                    for client in result.scalars().all():
                        try:
                            await send_trial_expiring_email(
                                to=client.notification_email or client.email,
                                name=client.name,
                                days_left=days_ahead,
                            )
                            logger.info(f"Trial expiry warning ({days_ahead}d) sent to {client.email}")
                        except Exception as e:
                            logger.error(f"Failed to send trial expiry email to {client.email}: {e}")

                # ── Monthly minute reset (runs on the 1st, resets all) ──
                if now.day == 1 and now.hour < 6:
                    await db.execute(
                        update(Client)
                        .where(Client.plan_minutes_used > 0)
                        .values(plan_minutes_used=0)
                    )
                    await db.commit()
                    logger.info("Monthly plan_minutes_used reset completed")

        except _asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduled tasks error: {e}")
            await _asyncio.sleep(60)  # retry after 1 min on error


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Safety checks ────────────────────────────────────────────────
    if settings.is_production and settings.SECRET_KEY == "change-me-in-production":
        raise RuntimeError(
            "FATAL: SECRET_KEY is set to the default value. "
            "Set a strong random SECRET_KEY environment variable before running in production."
        )
    if settings.is_production and settings.INTERNAL_API_KEY == "change-me-in-production":
        raise RuntimeError(
            "FATAL: INTERNAL_API_KEY is set to the default value. "
            "Set a strong random INTERNAL_API_KEY environment variable before running in production."
        )

    logger.info("Omniweb Agent Engine starting up")
    logger.info(f"ElevenLabs configured: {settings.elevenlabs_configured}")
    logger.info(f"Twilio configured: {settings.twilio_configured}")
    logger.info(f"OpenAI configured: {settings.openai_configured}")

    # Start background scheduler
    scheduler_task = _asyncio.create_task(_scheduled_tasks())
    logger.info("Background scheduler started (trial warnings + monthly reset)")

    yield

    scheduler_task.cancel()
    try:
        await scheduler_task
    except _asyncio.CancelledError:
        pass
    logger.info("Omniweb Agent Engine shutting down")
    await engine.dispose()


app = FastAPI(
    title="Omniweb Agent Engine",
    description="Multi-tenant AI telephony + text chat platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
)

# CORS — dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Internal-Key"],
)


# ── Security Headers Middleware ───────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Rate Limiting Middleware ──────────────────────────────────────────────────
# Simple in-memory rate limiter for auth endpoints.
# For production at scale, swap to Redis-backed (e.g. slowapi + redis).

import time
from collections import defaultdict

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX_AUTH = 10  # max auth requests per window per IP
_RATE_LIMIT_MAX_GENERAL = 120  # max general API requests per window per IP


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting. Stricter on auth endpoints."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        now = time.time()

        # Determine limit based on path
        if any(
            auth_path in path
            for auth_path in [
                "/auth/login",
                "/auth/signup",
                "/auth/forgot-password",
                "/auth/reset-password",
                "/auth/accept-invite",
            ]
        ):
            limit = _RATE_LIMIT_MAX_AUTH
            key = f"auth:{client_ip}"
        elif path.startswith("/api/"):
            limit = _RATE_LIMIT_MAX_GENERAL
            key = f"api:{client_ip}"
        else:
            return await call_next(request)

        # Clean old entries and check
        _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < _RATE_LIMIT_WINDOW]

        if len(_rate_limit_store[key]) >= limit:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
            )

        _rate_limit_store[key].append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

# ── Register routers ──────────────────────────────────────────────────────────
# All API routes live under /api/* so the ingress can cleanly separate
# backend requests from frontend routes (which share the same domain).

API_PREFIX = "/api"

# Auth
app.include_router(auth.router, prefix=API_PREFIX)

# Webhooks (no auth — URLs configured in ElevenLabs/Stripe dashboards)
app.include_router(webhooks_elevenlabs.router, prefix=API_PREFIX)
app.include_router(webhooks_stripe.router, prefix=API_PREFIX)
app.include_router(webhooks_tools.router, prefix=API_PREFIX)

# Data API
app.include_router(calls.router, prefix=API_PREFIX)
app.include_router(leads.router, prefix=API_PREFIX)
app.include_router(numbers.router, prefix=API_PREFIX)
app.include_router(agent_config.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(automations.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(industry.router, prefix=API_PREFIX)
app.include_router(knowledge_base.router, prefix=API_PREFIX)
app.include_router(templates.router, prefix=API_PREFIX)
app.include_router(embed.router, prefix=API_PREFIX)
app.include_router(subscribe.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)

# Admin API
app.include_router(admin.router, prefix=API_PREFIX)


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "service": "omniweb-agent-engine",
        "version": "2.0.0",
        "elevenlabs_configured": settings.elevenlabs_configured,
        "twilio_configured": settings.twilio_configured,
        "openai_configured": settings.openai_configured,
    }


@app.post("/api/seed")
async def run_seed(x_api_key: str = Header(...)):
    """One-shot seed endpoint — protected by INTERNAL_API_KEY.

    Call with: curl -X POST https://<domain>/api/seed -H "X-Api-Key: <key>"
    """
    if x_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    import asyncio
    import importlib

    # Import and run the seed function
    seed_module = importlib.import_module("seed")
    await seed_module.seed()
    return {"ok": True, "message": "Seed complete"}

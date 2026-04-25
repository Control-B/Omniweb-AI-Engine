"""Omniweb Agent Engine — FastAPI application.

This is the DATA PLANE. It:
  - Manages multi-tenant client accounts and auth
  - Composes per-tenant system prompts (prompt engine)
  - Mints Retell web-call tokens for the browser voice widget
  - Receives Retell webhooks (call ended / analyzed) and tool webhooks
  - Serves call history, transcripts, leads to the dashboard
  - Handles Stripe billing webhooks
  - Manages phone numbers (Twilio purchase; Retell binds in dashboard)
  - Sends SMS via Twilio
  - Provides widget configuration for voice + text surfaces
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine, get_database_configuration_error
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
    deepgram,
    embed,
    industry,
    knowledge_base,
    leads,
    numbers,
    retell,
    shopify,
    shopify_webhooks,
    site_templates,
    subscribe,
    templates,
    webhooks,
    webhooks_retell,
    webhooks_stripe,
    webhooks_tools,
)

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


import asyncio as _asyncio


async def probe_database() -> tuple[bool, str | None]:
    """Verify the application can reach Postgres."""
    config_error = get_database_configuration_error()
    if config_error:
        logger.error(f"Database configuration error: {config_error}")
        return False, config_error

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        logger.error(f"Database probe failed: {exc}")
        return False, str(exc)


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
    logger.info(f"Retell configured: {settings.retell_configured}")
    logger.info(f"Deepgram configured: {settings.deepgram_configured}")
    logger.info(f"Twilio configured: {settings.twilio_configured}")
    logger.info(f"OpenAI configured: {settings.openai_configured}")

    database_ok, database_error = await probe_database()
    if not database_ok:
        message = "Database connectivity check failed during startup."
        logger.warning(
            f"{message} Continuing startup so the service can answer liveness probes. "
            f"Database error: {database_error or 'unknown database error'}"
        )
    else:
        logger.info("Database connectivity check passed")

    # Start background scheduler
    scheduler_task = None
    if database_ok:
        scheduler_task = _asyncio.create_task(_scheduled_tasks())
        logger.info("Background scheduler started (trial warnings + monthly reset)")
    else:
        logger.warning("Background scheduler skipped because the database probe failed")

    yield

    if scheduler_task is not None:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except _asyncio.CancelledError:
            pass
    logger.info("Omniweb Agent Engine shutting down")
    if engine is not None:
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
    allow_origin_regex=r"https?://.*",
    allow_credentials=False,
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


class CanonicalHostMiddleware(BaseHTTPMiddleware):
    """Redirect requests from non-canonical engine hosts to the intended public hosts."""

    async def dispatch(self, request: Request, call_next):
        forwarded_host = request.headers.get("x-forwarded-host")
        raw_host = forwarded_host or request.headers.get("host", "")
        request_host = raw_host.split(",")[0].strip().split(":")[0].lower()

        if request_host in {host.lower() for host in settings.NON_CANONICAL_ENGINE_HOSTS}:
            path = request.url.path
            query = f"?{request.url.query}" if request.url.query else ""

            if path.startswith("/api") or path == "/health":
                return await call_next(request)

            return RedirectResponse(f"{settings.PLATFORM_URL.rstrip('/')}/admin", status_code=302)

        return await call_next(request)


app.add_middleware(CanonicalHostMiddleware)


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

# Webhooks (no auth — URLs configured in Retell / Stripe dashboards)
app.include_router(webhooks_retell.router, prefix=API_PREFIX)
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
app.include_router(retell.router, prefix=API_PREFIX)
app.include_router(deepgram.router, prefix=API_PREFIX)
app.include_router(templates.router, prefix=API_PREFIX)
app.include_router(shopify.router, prefix=API_PREFIX)
app.include_router(shopify_webhooks.router, prefix=API_PREFIX)
app.include_router(site_templates.router, prefix=API_PREFIX)
app.include_router(embed.router, prefix=API_PREFIX)
app.include_router(subscribe.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)

# Admin API
app.include_router(admin.router, prefix=API_PREFIX)


@app.get("/")
async def root_redirect():
    """Redirect bare engine URL to the Omniweb admin dashboard."""
    return RedirectResponse(f"{settings.PLATFORM_URL.rstrip('/')}/admin", status_code=302)


@app.get("/health")
async def health() -> dict:
    payload = {
        "ok": True,
        "service": "omniweb-agent-engine",
        "version": "2.0.0",
        "retell_configured": settings.retell_configured,
        "deepgram_configured": settings.deepgram_configured,
        "twilio_configured": settings.twilio_configured,
        "openai_configured": settings.openai_configured,
        "database_configured": settings.database_configured,
        "database_ok": False,
    }

    database_ok, database_error = await probe_database()
    if database_ok:
        payload["database_ok"] = True
        return payload

    payload["database_error"] = database_error
    payload["ok"] = True
    payload["status"] = "degraded"
    return payload


@app.get("/readyz")
async def readiness() -> dict:
    payload = {
        "ok": True,
        "service": "omniweb-agent-engine",
        "database_ok": False,
    }

    database_ok, database_error = await probe_database()
    if database_ok:
        payload["database_ok"] = True
        return payload

    payload["ok"] = False
    payload["database_error"] = database_error
    return JSONResponse(status_code=503, content=payload)


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


# ── Static files (storefront widget JS) ──────────────────────────────────────
import os as _os
from fastapi.staticfiles import StaticFiles as _StaticFiles

_static_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "static")
if _os.path.isdir(_static_dir):
    app.mount("/static", _StaticFiles(directory=_static_dir), name="static")

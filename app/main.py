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

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging, get_logger

# Import all route modules
from app.api.routes import (
    admin,
    agent_config,
    analytics,
    auth,
    calls,
    chat,
    leads,
    numbers,
    templates,
    webhooks_elevenlabs,
    webhooks_stripe,
)

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Omniweb Agent Engine starting up")
    logger.info(f"ElevenLabs configured: {settings.elevenlabs_configured}")
    logger.info(f"Twilio configured: {settings.twilio_configured}")
    logger.info(f"OpenAI configured: {settings.openai_configured}")
    yield
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
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
# All API routes live under /api/* so the ingress can cleanly separate
# backend requests from frontend routes (which share the same domain).

API_PREFIX = "/api"

# Auth
app.include_router(auth.router, prefix=API_PREFIX)

# Webhooks (no auth — URLs configured in ElevenLabs/Stripe dashboards)
app.include_router(webhooks_elevenlabs.router, prefix=API_PREFIX)
app.include_router(webhooks_stripe.router, prefix=API_PREFIX)

# Data API
app.include_router(calls.router, prefix=API_PREFIX)
app.include_router(leads.router, prefix=API_PREFIX)
app.include_router(numbers.router, prefix=API_PREFIX)
app.include_router(agent_config.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(templates.router, prefix=API_PREFIX)

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

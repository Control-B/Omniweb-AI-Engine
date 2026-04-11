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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging, get_logger

# Import all route modules
from app.api.routes import (
    agent_config,
    analytics,
    auth,
    calls,
    chat,
    leads,
    numbers,
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
    docs_url="/docs" if not settings.is_production else None,
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

# Auth
app.include_router(auth.router)

# Webhooks (no auth — URLs configured in ElevenLabs/Stripe dashboards)
app.include_router(webhooks_elevenlabs.router)
app.include_router(webhooks_stripe.router)

# Data API
app.include_router(calls.router)
app.include_router(leads.router)
app.include_router(numbers.router)
app.include_router(agent_config.router)
app.include_router(analytics.router)
app.include_router(chat.router)


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

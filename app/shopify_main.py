"""Omniweb Shopify Service — isolated FastAPI application.

This runs in its own container so that Shopify-specific traffic and failures
are completely isolated from the core AI engine.  It shares the same database,
Redis, and service code but only exposes Shopify routes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger

from app.api.routes import shopify
from app.api.routes import shopify_webhooks

settings = get_settings()
configure_logging()
logger = get_logger(__name__)

API_PREFIX = "/api"


# ── Lifespan ─────────────────────────────────────────────────────────────────

async def _probe_database() -> tuple[bool, str | None]:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        logger.error(f"Database probe failed: {exc}")
        return False, str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Omniweb Shopify Service starting up")

    db_ok, db_err = await _probe_database()
    if not db_ok:
        msg = "FATAL: Database connectivity check failed during startup."
        if settings.is_production:
            raise RuntimeError(f"{msg} {db_err or 'unknown'}")
        logger.warning(f"{msg} Continuing (non-production).")
    else:
        logger.info("Database connectivity check passed")

    # Start session cleanup background task
    import asyncio
    cleanup_task = None
    if db_ok:
        cleanup_task = asyncio.create_task(_session_cleanup_loop())
        logger.info("Session cleanup task started (runs every 6 hours)")

    yield

    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("Omniweb Shopify Service shutting down")
    await engine.dispose()


async def _session_cleanup_loop():
    """Purge stale Shopify assistant sessions older than 7 days."""
    import asyncio
    from datetime import timedelta
    from sqlalchemy import delete
    from app.models.models import ShopifyAssistantSession
    from app.services.shopify_assistant_service import utcnow

    while True:
        try:
            await asyncio.sleep(6 * 3600)  # every 6 hours
            cutoff = utcnow() - timedelta(days=7)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    delete(ShopifyAssistantSession).where(
                        ShopifyAssistantSession.last_seen_at < cutoff,
                    )
                )
                await db.commit()
                deleted = result.rowcount  # type: ignore[attr-defined]
                if deleted:
                    logger.info(f"Session cleanup: purged {deleted} stale sessions")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
            await asyncio.sleep(60)


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Omniweb Shopify Service",
    description="Isolated Shopify commerce-assistant microservice",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Internal-Key"],
)

# Rate limiting on public storefront endpoints
from app.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=60, burst=10)


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    db_ok, db_err = await _probe_database()
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status": "healthy" if db_ok else "degraded",
            "service": "shopify",
            "database": "ok" if db_ok else db_err,
        },
    )


# ── Routes ───────────────────────────────────────────────────────────────────

app.include_router(shopify.router, prefix=API_PREFIX)
app.include_router(shopify_webhooks.router, prefix=API_PREFIX)

# ── Static files (storefront widget JS) ──────────────────────────────────────

import os
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

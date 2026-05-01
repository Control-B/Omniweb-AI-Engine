"""Dedicated maintenance scheduler for periodic platform jobs.

Runs outside the web process so tasks are not duplicated across multiple
``uvicorn`` workers or replicas.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select, update

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.models.models import Client
from app.services.email_service import send_trial_expiring_email

settings = get_settings()
configure_logging()
logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 6 * 3600


async def run_maintenance_cycle(now: datetime | None = None) -> None:
    """Execute one maintenance pass.

    Current jobs:
    - trial expiry warning emails (3 days and 1 day remaining)
    - monthly `plan_minutes_used` reset near the start of the month
    """
    current_time = now or datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        for days_ahead in (3, 1):
            window_start = current_time + timedelta(days=days_ahead - 0.25)
            window_end = current_time + timedelta(days=days_ahead + 0.25)
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
                    logger.info(
                        "Trial expiry warning sent",
                        client_id=str(client.id),
                        email=client.email,
                        days_left=days_ahead,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to send trial expiry email",
                        client_id=str(client.id),
                        email=client.email,
                        days_left=days_ahead,
                        error=str(exc),
                    )

        if current_time.day == 1 and current_time.hour < 6:
            result = await db.execute(
                update(Client)
                .where(Client.plan_minutes_used > 0)
                .values(plan_minutes_used=0)
            )
            await db.commit()
            logger.info(
                "Monthly plan_minutes_used reset completed",
                rows_updated=result.rowcount,
            )


async def run_scheduler_loop(poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS) -> None:
    """Run maintenance forever in a dedicated worker process."""
    logger.info(
        "Maintenance scheduler starting",
        environment=settings.ENVIRONMENT,
        poll_interval_seconds=poll_interval_seconds,
    )

    try:
        while True:
            try:
                await run_maintenance_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Maintenance scheduler cycle failed", error=str(exc))
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(poll_interval_seconds)
    finally:
        await engine.dispose()
        logger.info("Maintenance scheduler stopped")


async def run_once() -> None:
    """Execute a single maintenance cycle and exit."""
    logger.info("Maintenance scheduler single-run start")
    try:
        await run_maintenance_cycle()
    finally:
        await engine.dispose()
        logger.info("Maintenance scheduler single-run complete")

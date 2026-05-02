"""Tenant AI Scheduling API backed by internal Cal.diy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.services.calcom_scheduling_service import CalcomSchedulingService, SchedulingServiceError

logger = get_logger(__name__)
router = APIRouter(prefix="/scheduling", tags=["scheduling"])


class SchedulingConfigPatch(BaseModel):
    calcom_user_id: str | None = None
    default_event_type_id: str | None = None
    event_type_ids: list[str] | None = None
    booking_mode: str | None = Field(None, pattern="^(manual|ai-assisted|ai auto-book)$")
    status: str | None = Field(None, pattern="^(connected|disabled|error)$")


class BookingRequest(BaseModel):
    event_type_id: str | None = None
    start_time: str
    timezone: str = "America/New_York"
    name: str
    email: str
    phone: str | None = None
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CancelBookingRequest(BaseModel):
    booking_uid: str
    reason: str | None = None


def _tenant_id(current: dict) -> UUID:
    try:
        return UUID(str(current["client_id"]))
    except Exception as exc:
        raise HTTPException(401, "Invalid tenant session") from exc


def _default_date_range() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), (now + timedelta(days=7)).strftime("%Y-%m-%d")


@router.get("/status")
async def get_scheduling_status(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = CalcomSchedulingService(db)
    return await service.status(_tenant_id(current))


@router.patch("/config")
async def update_scheduling_config(
    body: SchedulingConfigPatch,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = CalcomSchedulingService(db)
    return await service.update_config(_tenant_id(current), body.model_dump(exclude_none=True))


@router.get("/event-types")
async def list_event_types(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = CalcomSchedulingService(db)
    return {"eventTypes": await service.get_event_types(_tenant_id(current))}


@router.get("/availability")
async def preview_availability(
    event_type_id: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    timezone_name: str = Query("America/New_York", alias="timezone"),
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    range_start, range_end = _default_date_range()
    service = CalcomSchedulingService(db)
    try:
        slots = await service.get_available_slots(
            _tenant_id(current),
            event_type_id=event_type_id,
            date_range={"start": start or range_start, "end": end or range_end},
            timezone_name=timezone_name,
        )
    except SchedulingServiceError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"slots": slots}


@router.get("/bookings")
async def list_recent_bookings(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = CalcomSchedulingService(db)
    return {"bookings": await service.recent_bookings(_tenant_id(current), limit=25)}


@router.post("/bookings")
async def create_booking(
    body: BookingRequest,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = CalcomSchedulingService(db)
    try:
        return await service.create_booking(
            tenant_id=_tenant_id(current),
            name=body.name,
            email=body.email,
            phone=body.phone,
            start_time=body.start_time,
            event_type_id=body.event_type_id,
            timezone_name=body.timezone,
            topic=body.topic,
            metadata=body.metadata,
        )
    except SchedulingServiceError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/bookings/cancel")
async def cancel_booking(
    body: CancelBookingRequest,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = CalcomSchedulingService(db)
    try:
        return await service.cancel_booking(_tenant_id(current), body.booking_uid, body.reason or "")
    except SchedulingServiceError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc

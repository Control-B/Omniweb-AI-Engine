"""Cal.com calendar service — appointment booking & availability.

Provides two main capabilities used by the AI agent's tool system:
  1. check_availability  — query open time slots
  2. book_appointment    — create a booking

Requires CALCOM_API_KEY in the environment.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_BASE_URL = settings.CALCOM_API_URL  # https://api.cal.com/v2


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.CALCOM_API_KEY}",
        "Content-Type": "application/json",
        "cal-api-version": "2024-08-13",
    }


async def check_availability(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    event_type_id: int | None = None,
    duration_minutes: int = 30,
) -> list[dict[str, Any]]:
    """Return available time slots from Cal.com.

    Args:
        start_date: ISO date string (defaults to today).
        end_date: ISO date string (defaults to 7 days from start).
        event_type_id: Cal.com event type (defaults to CALCOM_EVENT_TYPE_ID).
        duration_minutes: Slot duration.

    Returns:
        List of ``{"start": "...", "end": "..."}`` slot dicts.
    """
    if not settings.calcom_configured:
        logger.warning("Cal.com not configured — returning empty availability")
        return []

    now = datetime.utcnow()
    start = start_date or now.strftime("%Y-%m-%d")
    end = end_date or (now + timedelta(days=7)).strftime("%Y-%m-%d")
    evt_id = event_type_id or settings.CALCOM_EVENT_TYPE_ID

    params = {
        "startTime": f"{start}T00:00:00Z",
        "endTime": f"{end}T23:59:59Z",
        "eventTypeId": evt_id,
        "duration": duration_minutes,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_BASE_URL}/slots",
            headers=_headers(),
            params=params,
        )

        if resp.status_code != 200:
            logger.error(
                "Cal.com availability error",
                status=resp.status_code,
                body=resp.text[:500],
            )
            return []

        data = resp.json()
        # Cal.com v2 returns {"data": {"slots": {"2024-01-15": [...]}}}
        slots_by_date = data.get("data", {}).get("slots", {})
        flat: list[dict[str, Any]] = []
        for date_key, day_slots in slots_by_date.items():
            for slot in day_slots:
                flat.append({
                    "start": slot.get("time", slot.get("start")),
                    "date": date_key,
                })

        logger.info(
            "Cal.com availability fetched",
            start=start,
            end=end,
            slot_count=len(flat),
        )
        return flat


async def book_appointment(
    *,
    name: str,
    email: str,
    phone: str = "",
    start_time: str,
    event_type_id: int | None = None,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Book an appointment via Cal.com.

    Args:
        name: Attendee full name.
        email: Attendee email.
        phone: Attendee phone (optional).
        start_time: ISO datetime for the appointment start.
        event_type_id: Cal.com event type (defaults to CALCOM_EVENT_TYPE_ID).
        notes: Additional notes from the conversation.
        metadata: Extra metadata (client_id, call_id, etc.).

    Returns:
        Booking confirmation dict with ``id``, ``uid``, ``startTime``, etc.
    """
    if not settings.calcom_configured:
        logger.warning("Cal.com not configured — returning stub booking")
        return {
            "status": "stub",
            "message": "Calendar not configured. Lead info captured — team will follow up manually.",
        }

    evt_id = event_type_id or settings.CALCOM_EVENT_TYPE_ID

    payload: dict[str, Any] = {
        "eventTypeId": evt_id,
        "start": start_time,
        "attendee": {
            "name": name,
            "email": email,
            "timeZone": "America/New_York",  # could be dynamic from agent context
        },
        "metadata": metadata or {},
    }

    if phone:
        payload["attendee"]["phoneNumber"] = phone

    if notes:
        payload["metadata"]["notes"] = notes

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_BASE_URL}/bookings",
            headers=_headers(),
            json=payload,
        )

        if resp.status_code not in (200, 201):
            logger.error(
                "Cal.com booking error",
                status=resp.status_code,
                body=resp.text[:500],
            )
            return {
                "status": "error",
                "message": "Sorry, I couldn't complete the booking right now. Let me capture your info so the team can follow up.",
            }

        booking = resp.json().get("data", resp.json())
        logger.info(
            "Cal.com booking created",
            booking_id=booking.get("id"),
            start=start_time,
            attendee=email,
        )
        return {
            "status": "confirmed",
            "booking_id": booking.get("id"),
            "uid": booking.get("uid"),
            "start_time": start_time,
            "message": f"Your appointment is confirmed for {start_time}. You'll receive a confirmation email at {email}.",
        }


async def cancel_booking(booking_uid: str, reason: str = "") -> dict[str, Any]:
    """Cancel a Cal.com booking."""
    if not settings.calcom_configured:
        return {"status": "error", "message": "Calendar not configured"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_BASE_URL}/bookings/{booking_uid}/cancel",
            headers=_headers(),
            json={"cancellationReason": reason} if reason else {},
        )

        if resp.status_code not in (200, 201):
            logger.error("Cal.com cancel error", status=resp.status_code)
            return {"status": "error", "message": "Could not cancel booking"}

        logger.info("Cal.com booking cancelled", uid=booking_uid)
        return {"status": "cancelled", "uid": booking_uid}

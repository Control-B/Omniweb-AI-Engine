"""Internal Cal.diy scheduling service.

Cal.diy is treated as a trusted private microservice. This module deliberately
does not send Cal.com API keys, browser cookies, or frontend credentials.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, SchedulingBooking, TenantSchedulingConfig
from app.services import email_service

logger = get_logger(__name__)
settings = get_settings()


class SchedulingServiceError(Exception):
    """User-safe scheduling error raised by the internal scheduler."""

    def __init__(self, message: str, *, code: str = "SCHEDULING_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_event_type_id(value: str | int | None) -> str:
    return str(value or "").strip()


def _event_type_payload_value(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _serialize_booking(booking: SchedulingBooking) -> dict[str, Any]:
    return {
        "id": str(booking.id),
        "calcomBookingId": booking.calcom_booking_id,
        "calcomBookingUid": booking.calcom_booking_uid,
        "eventTypeId": booking.event_type_id,
        "attendeeName": booking.attendee_name,
        "attendeeEmail": booking.attendee_email,
        "attendeePhone": booking.attendee_phone,
        "startTime": booking.start_time.isoformat() if booking.start_time else None,
        "endTime": booking.end_time.isoformat() if booking.end_time else None,
        "timezone": booking.timezone,
        "status": booking.status,
        "topic": booking.topic,
        "metadata": booking.metadata_json or {},
        "createdAt": booking.created_at.isoformat() if booking.created_at else None,
    }


class CalcomSchedulingService:
    """Tenant-aware wrapper around the private Cal.diy API."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_url = settings.CALCOM_INTERNAL_URL.rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.CALCOM_INTERNAL_SERVICE_HEADER:
            headers["X-Internal-Service"] = settings.CALCOM_INTERNAL_SERVICE_HEADER
        return headers

    async def get_or_create_config(self, tenant_id: UUID) -> TenantSchedulingConfig:
        result = await self.db.execute(
            select(TenantSchedulingConfig).where(TenantSchedulingConfig.tenant_id == tenant_id)
        )
        config = result.scalar_one_or_none()
        if config:
            return config

        config = TenantSchedulingConfig(
            tenant_id=tenant_id,
            default_event_type_id=(settings.CALCOM_EVENT_TYPE_ID or settings.CALCOM_DEFAULT_EVENT_TYPE_ID or None),
            event_type_ids=(
                [settings.CALCOM_EVENT_TYPE_ID or settings.CALCOM_DEFAULT_EVENT_TYPE_ID]
                if (settings.CALCOM_EVENT_TYPE_ID or settings.CALCOM_DEFAULT_EVENT_TYPE_ID)
                else []
            ),
            status="disabled",
        )
        self.db.add(config)
        await self.db.flush()
        return config

    async def update_config(self, tenant_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        config = await self.get_or_create_config(tenant_id)

        if "calcom_user_id" in payload:
            config.calcom_user_id = (payload.get("calcom_user_id") or "").strip() or None
        if "default_event_type_id" in payload:
            config.default_event_type_id = _coerce_event_type_id(payload.get("default_event_type_id")) or None
        if "event_type_ids" in payload and isinstance(payload["event_type_ids"], list):
            config.event_type_ids = [
                event_type_id
                for event_type_id in (_coerce_event_type_id(item) for item in payload["event_type_ids"])
                if event_type_id
            ]
        if "booking_mode" in payload and payload["booking_mode"] in {"manual", "ai-assisted", "ai auto-book"}:
            config.booking_mode = payload["booking_mode"]
        if "status" in payload and payload["status"] in {"connected", "disabled", "error"}:
            config.status = payload["status"]
        settings_json = dict(config.settings_json or {})
        settings_key_map = {
            "booking_url": "bookingUrl",
            "notification_email": "notificationEmail",
            "resend_from_email": "resendFromEmail",
            "resend_reply_to_email": "resendReplyToEmail",
            "appointment_instructions": "appointmentInstructions",
            "scheduling_behavior": "schedulingBehavior",
        }
        for payload_key, settings_key in settings_key_map.items():
            if payload_key in payload:
                value = payload.get(payload_key)
                if isinstance(value, str):
                    value = value.strip()
                if value:
                    settings_json[settings_key] = value
                else:
                    settings_json.pop(settings_key, None)
        config.settings_json = settings_json

        await self.db.flush()
        return await self.status(tenant_id, refresh_health=False)

    async def status(self, tenant_id: UUID, *, refresh_health: bool = True) -> dict[str, Any]:
        config = await self.get_or_create_config(tenant_id)
        settings_json = config.settings_json or {}
        resend_from_email = (
            str(settings_json.get("resendFromEmail") or "")
            if isinstance(settings_json, dict)
            else ""
        )
        email_identity = await email_service.resend_sender_identity_status(resend_from_email)
        health = await self.health_check(tenant_id) if refresh_health else {
            "ok": config.last_health_status == "connected",
            "status": config.last_health_status or config.status,
            "message": config.last_error,
        }
        event_types = await self.get_event_types(tenant_id) if health["ok"] else []
        recent_bookings = await self.recent_bookings(tenant_id)
        return {
            "status": "connected" if health["ok"] and config.status != "disabled" else config.status,
            "health": health,
            "config": {
                "calcomUserId": config.calcom_user_id,
                "defaultEventTypeId": config.default_event_type_id,
                "eventTypeIds": config.event_type_ids or [],
                "bookingMode": config.booking_mode,
                "status": config.status,
                "settings": settings_json,
            },
            "emailIdentity": email_identity,
            "internalUrlConfigured": bool(self.base_url),
            "eventTypes": event_types,
            "recentBookings": recent_bookings,
        }

    async def health_check(self, tenant_id: UUID) -> dict[str, Any]:
        config = await self.get_or_create_config(tenant_id)
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(f"{self.base_url}/health", headers=self.headers)
                if response.status_code == 404:
                    response = await client.get(f"{self.base_url}/event-types", headers=self.headers)
                response.raise_for_status()

            config.last_health_status = "connected"
            config.last_health_at = utcnow()
            config.last_error = None
            if config.status == "error":
                config.status = "connected"
            await self.db.flush()
            return {"ok": True, "status": "connected", "message": "Cal.diy is reachable internally."}
        except Exception as exc:
            logger.warning("Cal.diy health check failed", tenant_id=str(tenant_id), error=str(exc))
            config.last_health_status = "error"
            config.last_health_at = utcnow()
            config.last_error = "Cal.diy is not reachable from the Omniweb backend."
            if config.status != "disabled":
                config.status = "error"
            await self.db.flush()
            return {"ok": False, "status": "error", "message": config.last_error}

    async def get_event_types(self, tenant_id: UUID) -> list[dict[str, Any]]:
        config = await self.get_or_create_config(tenant_id)
        params: dict[str, Any] = {}
        if config.calcom_user_id:
            params["userId"] = config.calcom_user_id

        try:
            data = await self._request("GET", "/event-types", params=params)
        except SchedulingServiceError:
            return []

        raw_items = self._extract_list(data)
        allowed = set(self._allowed_event_type_ids(config))
        event_types: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            event_type_id = _coerce_event_type_id(item.get("id") or item.get("eventTypeId"))
            if allowed and event_type_id not in allowed:
                continue
            event_types.append({
                "id": event_type_id,
                "title": item.get("title") or item.get("name") or f"Event type {event_type_id}",
                "slug": item.get("slug"),
                "length": item.get("length") or item.get("duration"),
                "metadata": item,
            })
        return event_types

    async def get_available_slots(
        self,
        tenant_id: UUID,
        event_type_id: str | int | None = None,
        date_range: dict[str, str] | None = None,
        timezone_name: str = "America/New_York",
    ) -> list[dict[str, Any]]:
        config = await self.get_or_create_config(tenant_id)
        resolved_event_type_id = self._resolve_event_type_id(config, event_type_id)
        start_time, end_time = self._date_range_to_window(date_range)

        params = {
            "eventTypeId": _event_type_payload_value(resolved_event_type_id),
            "startTime": start_time,
            "endTime": end_time,
            "timeZone": timezone_name,
        }
        if config.calcom_user_id:
            params["userId"] = config.calcom_user_id

        data = await self._request("GET", "/slots", params=params)
        slots = self._extract_slots(data)
        return slots[:12]

    async def create_booking(
        self,
        *,
        tenant_id: UUID,
        name: str,
        email: str,
        start_time: str,
        event_type_id: str | int | None = None,
        timezone_name: str = "America/New_York",
        phone: str | None = None,
        topic: str | None = None,
        metadata: dict[str, Any] | None = None,
        lead_id: UUID | None = None,
    ) -> dict[str, Any]:
        if not name.strip() or not email.strip():
            raise SchedulingServiceError("I need a name and email before I can book that appointment.", code="MISSING_ATTENDEE")
        if not _parse_datetime(start_time):
            raise SchedulingServiceError(
                "Please confirm one of the available appointment times before I book it.",
                code="MISSING_START_TIME",
            )

        config = await self.get_or_create_config(tenant_id)
        resolved_event_type_id = self._resolve_event_type_id(config, event_type_id)
        payload: dict[str, Any] = {
            "eventTypeId": _event_type_payload_value(resolved_event_type_id),
            "start": start_time,
            "attendee": {
                "name": name.strip(),
                "email": email.strip(),
                "timeZone": timezone_name,
            },
            "metadata": {
                **(metadata or {}),
                "tenant_id": str(tenant_id),
                "source": "omniweb_ai",
            },
        }
        if phone:
            payload["attendee"]["phoneNumber"] = phone
        if topic:
            payload["metadata"]["topic"] = topic
        if config.calcom_user_id:
            payload["userId"] = config.calcom_user_id

        try:
            data = await self._request("POST", "/bookings", json=payload)
        except SchedulingServiceError as exc:
            if exc.status_code in {409, 422}:
                raise SchedulingServiceError(
                    "That time is no longer available. Please choose another available slot.",
                    code="SLOT_UNAVAILABLE",
                    status_code=409,
                ) from exc
            raise

        booking_data = data.get("data", data) if isinstance(data, dict) else {}
        booking = SchedulingBooking(
            tenant_id=tenant_id,
            lead_id=lead_id,
            calcom_booking_id=_coerce_event_type_id(booking_data.get("id")) or None,
            calcom_booking_uid=booking_data.get("uid") or booking_data.get("bookingUid"),
            event_type_id=resolved_event_type_id,
            attendee_name=name.strip(),
            attendee_email=email.strip(),
            attendee_phone=phone,
            start_time=_parse_datetime(booking_data.get("startTime") or booking_data.get("start") or start_time),
            end_time=_parse_datetime(booking_data.get("endTime") or booking_data.get("end")),
            timezone=timezone_name,
            status="confirmed",
            topic=topic,
            metadata_json=payload["metadata"],
        )
        self.db.add(booking)
        await self.db.flush()
        return {
            "status": "confirmed",
            "booking": _serialize_booking(booking),
            "message": f"Your appointment is confirmed for {start_time}. You'll receive a confirmation email at {email}.",
        }

    async def cancel_booking(self, tenant_id: UUID, booking_uid: str, reason: str = "") -> dict[str, Any]:
        result = await self.db.execute(
            select(SchedulingBooking).where(
                SchedulingBooking.tenant_id == tenant_id,
                SchedulingBooking.calcom_booking_uid == booking_uid,
            )
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise SchedulingServiceError("I couldn't find that booking for this tenant.", code="BOOKING_NOT_FOUND", status_code=404)

        await self._request(
            "POST",
            f"/bookings/{booking_uid}/cancel",
            json={"cancellationReason": reason} if reason else {},
        )
        booking.status = "cancelled"
        await self.db.flush()
        return {"status": "cancelled", "booking": _serialize_booking(booking)}

    async def recent_bookings(self, tenant_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(SchedulingBooking)
            .where(SchedulingBooking.tenant_id == tenant_id)
            .order_by(desc(SchedulingBooking.created_at))
            .limit(limit)
        )
        return [_serialize_booking(booking) for booking in result.scalars().all()]

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    **kwargs,
                )
        except httpx.RequestError as exc:
            raise SchedulingServiceError(
                "The scheduling service is temporarily unavailable. Our team can follow up manually.",
                code="CALDIY_UNREACHABLE",
                status_code=503,
            ) from exc

        if response.status_code >= 400:
            logger.warning(
                "Cal.diy internal API error",
                status=response.status_code,
                body=response.text[:500],
            )
            raise SchedulingServiceError(
                "The scheduling service could not complete that request right now.",
                code="CALDIY_REQUEST_FAILED",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise SchedulingServiceError(
                "The scheduling service returned an invalid response.",
                code="CALDIY_INVALID_RESPONSE",
                status_code=502,
            ) from exc

    def _allowed_event_type_ids(self, config: TenantSchedulingConfig) -> list[str]:
        allowed = [_coerce_event_type_id(item) for item in (config.event_type_ids or [])]
        default_id = _coerce_event_type_id(config.default_event_type_id or settings.CALCOM_EVENT_TYPE_ID or settings.CALCOM_DEFAULT_EVENT_TYPE_ID)
        if default_id and default_id not in allowed:
            allowed.append(default_id)
        return [item for item in allowed if item]

    def _resolve_event_type_id(self, config: TenantSchedulingConfig, event_type_id: str | int | None) -> str:
        requested = _coerce_event_type_id(event_type_id)
        default_id = _coerce_event_type_id(config.default_event_type_id or settings.CALCOM_EVENT_TYPE_ID or settings.CALCOM_DEFAULT_EVENT_TYPE_ID)
        resolved = requested or default_id
        if not resolved:
            raise SchedulingServiceError(
                "AI Scheduling is not connected to a tenant event type yet.",
                code="SCHEDULING_NOT_CONFIGURED",
                status_code=409,
            )

        allowed = set(self._allowed_event_type_ids(config))
        if allowed and resolved not in allowed:
            raise SchedulingServiceError(
                "That event type is not configured for this tenant.",
                code="EVENT_TYPE_NOT_ALLOWED",
                status_code=403,
            )
        return resolved

    def _date_range_to_window(self, date_range: dict[str, str] | None) -> tuple[str, str]:
        now = utcnow()
        start = (date_range or {}).get("start") or now.strftime("%Y-%m-%d")
        end = (date_range or {}).get("end") or (now + timedelta(days=7)).strftime("%Y-%m-%d")
        if "T" not in start:
            start = f"{start}T00:00:00Z"
        if "T" not in end:
            end = f"{end}T23:59:59Z"
        return start, end

    def _extract_list(self, data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data", "eventTypes", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    nested = self._extract_list(value)
                    if nested:
                        return nested
        return []

    def _extract_slots(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        container = data.get("data", data)
        raw_slots = container.get("slots", container) if isinstance(container, dict) else container
        slots: list[dict[str, Any]] = []
        if isinstance(raw_slots, dict):
            for date_key, day_slots in raw_slots.items():
                if not isinstance(day_slots, list):
                    continue
                for slot in day_slots:
                    if isinstance(slot, dict):
                        start = slot.get("time") or slot.get("start") or slot.get("startTime")
                        end = slot.get("end") or slot.get("endTime")
                        slots.append({"start": start, "end": end, "date": date_key})
        elif isinstance(raw_slots, list):
            for slot in raw_slots:
                if isinstance(slot, dict):
                    slots.append({
                        "start": slot.get("time") or slot.get("start") or slot.get("startTime"),
                        "end": slot.get("end") or slot.get("endTime"),
                        "date": slot.get("date"),
                    })
        return [slot for slot in slots if slot.get("start")]

    async def _get_agent_timezone(self, tenant_id: UUID) -> str:
        result = await self.db.execute(select(AgentConfig).where(AgentConfig.client_id == tenant_id))
        config = result.scalar_one_or_none()
        return config.timezone if config and config.timezone else "America/New_York"

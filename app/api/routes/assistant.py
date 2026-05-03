"""Public assistant action endpoints used by the Omniweb widget/backend."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.services.assistant_scheduling_service import (
    SchedulePayload,
    create_schedule_request,
    send_schedule_emails,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])


class AssistantScheduleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")
    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=120)
    visitor_name: str = Field(alias="visitorName", min_length=1, max_length=255)
    visitor_email: EmailStr = Field(alias="visitorEmail")
    visitor_phone: str | None = Field(None, alias="visitorPhone", max_length=30)
    requested_service: str | None = Field(None, alias="requestedService", max_length=255)
    preferred_date: str | None = Field(None, alias="preferredDate", max_length=80)
    preferred_time: str | None = Field(None, alias="preferredTime", max_length=80)
    notes: str | None = Field(None, max_length=4000)
    source_url: str | None = Field(None, alias="sourceUrl", max_length=2048)


@router.post("/schedule")
async def schedule_assistant_appointment(
    body: AssistantScheduleRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create an appointment request and return the tenant's Cal.com DIY link."""
    try:
        appointment, client, agent, duplicate = await create_schedule_request(
            db,
            SchedulePayload(
                tenant_id=body.tenant_id,
                conversation_id=body.conversation_id,
                visitor_name=body.visitor_name,
                visitor_email=str(body.visitor_email),
                visitor_phone=body.visitor_phone,
                requested_service=body.requested_service,
                preferred_date=body.preferred_date,
                preferred_time=body.preferred_time,
                notes=body.notes,
                source_url=body.source_url,
            ),
        )
        email_status = {"visitorConfirmation": False, "businessNotification": False}
        if not duplicate:
            email_status = await send_schedule_emails(db, appointment=appointment, client=client, agent=agent)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(500, "Failed to prepare appointment scheduling") from exc

    return {
        "success": True,
        "bookingUrl": appointment.booking_url,
        "message": "I found the booking page. You can choose the best available time here.",
        "appointmentRequestId": str(appointment.id),
        "emailStatus": email_status,
        "duplicate": duplicate,
    }

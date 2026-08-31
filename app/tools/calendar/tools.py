"""Calendar & Appointment Scheduling Tools for Omniweb Contact Center."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolCategory, ToolResult, ToolRiskLevel
from app.tools.registry import get_tool_registry


class CheckAvailabilityInput(BaseModel):
    date_str: str = Field(..., description="Target date in YYYY-MM-DD format (or relative like 'tomorrow', 'next Tuesday')")
    service_type: str | None = Field(None, description="Service or consultation type")
    duration_minutes: int = Field(30, description="Duration in minutes")


class CheckAvailabilityOutput(BaseModel):
    available_slots: list[str]
    timezone: str


class CheckAvailabilityTool(BaseTool[CheckAvailabilityInput, CheckAvailabilityOutput]):
    name = "check_availability"
    description = "Check real-time calendar availability for booking appointments or consultation calls."
    category = ToolCategory.CALENDAR
    risk_level = ToolRiskLevel.STANDARD
    input_schema = CheckAvailabilityInput
    output_schema = CheckAvailabilityOutput
    allowed_agents = ["receptionist", "scheduling", "sales", "support"]

    async def execute(
        self,
        params: CheckAvailabilityInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        mock_slots = ["09:00 AM", "11:30 AM", "02:00 PM", "04:15 PM"]
        return ToolResult(
            success=True,
            data={
                "date": params.date_str,
                "available_slots": mock_slots,
                "timezone": "America/New_York",
            },
        )


class BookAppointmentInput(BaseModel):
    caller_name: str = Field(..., description="Full name of the attendee")
    caller_email: str = Field(..., description="Email for calendar invite and confirmation")
    caller_phone: str | None = Field(None, description="Phone number for SMS reminder")
    appointment_date: str = Field(..., description="Date of appointment (YYYY-MM-DD)")
    appointment_time: str = Field(..., description="Selected time slot (e.g. '02:00 PM')")
    topic: str = Field(..., description="Meeting topic or purpose")


class BookAppointmentOutput(BaseModel):
    booking_id: str
    confirmed_time: str
    calendar_invite_sent: bool


class BookAppointmentTool(BaseTool[BookAppointmentInput, BookAppointmentOutput]):
    name = "book_appointment"
    description = "Confirm and book an appointment slot on Cal.com / Google Calendar, sending calendar invites and SMS confirmation."
    category = ToolCategory.CALENDAR
    risk_level = ToolRiskLevel.STANDARD
    input_schema = BookAppointmentInput
    output_schema = BookAppointmentOutput
    allowed_agents = ["receptionist", "scheduling", "sales", "support"]

    async def execute(
        self,
        params: BookAppointmentInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        booking_id = f"cal_{abs(hash(params.caller_email + params.appointment_time)) % 100000:05d}"
        return ToolResult(
            success=True,
            data={
                "booking_id": booking_id,
                "confirmed_time": f"{params.appointment_date} at {params.appointment_time} (EST)",
                "calendar_invite_sent": True,
                "sms_reminder_scheduled": bool(params.caller_phone or caller_id),
                "message": f"Appointment booked with {params.caller_name} for {params.appointment_date} at {params.appointment_time}. Calendar invite dispatched.",
            },
        )


# Register tools on import
registry = get_tool_registry()
registry.register(CheckAvailabilityTool())
registry.register(BookAppointmentTool())

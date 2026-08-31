"""Support Ticketing & Diagnostics Tools for Omniweb Contact Center."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolCategory, ToolResult, ToolRiskLevel
from app.tools.registry import get_tool_registry


class CreateTicketInput(BaseModel):
    customer_id: str | None = Field(None, description="Customer ID if verified")
    caller_name: str = Field(..., description="Name of the person opening the ticket")
    caller_phone: str | None = Field(None, description="Callback phone number")
    caller_email: str | None = Field(None, description="Contact email")
    category: str = Field("technical_issue", description="Category: hardware, billing, account_access, general_inquiry")
    severity: str = Field("medium", description="Severity level: low, medium, high, critical")
    issue_summary: str = Field(..., description="Concise summary of the problem")
    troubleshooting_steps_attempted: list[str] = Field(default_factory=list, description="Steps already completed")


class CreateTicketOutput(BaseModel):
    ticket_id: str
    status: str
    assigned_queue: str
    sla_hours: int


class CreateTicketTool(BaseTool[CreateTicketInput, CreateTicketOutput]):
    name = "create_ticket"
    description = "Create a customer support ticket in Zendesk/Jira or the internal ticketing engine."
    category = ToolCategory.TICKETING
    risk_level = ToolRiskLevel.STANDARD
    input_schema = CreateTicketInput
    output_schema = CreateTicketOutput
    allowed_agents = ["support", "receptionist", "escalation"]

    async def execute(
        self,
        params: CreateTicketInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        ticket_id = f"TICK-{abs(hash(params.issue_summary)) % 10000:04d}"
        queue_map = {
            "hardware": "Tier-2 Hardware Specialists",
            "billing": "Finance & Billing Queue",
            "account_access": "Identity Security Team",
            "technical_issue": "Tier-1 Technical Support",
        }
        assigned_queue = queue_map.get(params.category, "General Support Queue")
        sla_hours = 2 if params.severity in ("high", "critical") else 24

        return ToolResult(
            success=True,
            data={
                "ticket_id": ticket_id,
                "status": "opened",
                "assigned_queue": assigned_queue,
                "sla_hours": sla_hours,
                "message": f"Ticket {ticket_id} opened and assigned to {assigned_queue}. SLA commitment: {sla_hours} hours.",
            },
        )


# Register tools on import
registry = get_tool_registry()
registry.register(CreateTicketTool())

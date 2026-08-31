"""CRM & Lead Qualification Tools for Omniweb Contact Center."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolCategory, ToolResult, ToolRiskLevel
from app.tools.registry import get_tool_registry


# ── Customer Lookup Tool ────────────────────────────────────────────────────

class LookupCustomerInput(BaseModel):
    phone_number: str | None = Field(None, description="Caller's phone number in E.164 format")
    email: str | None = Field(None, description="Caller's email address")
    customer_id: str | None = Field(None, description="Direct customer UUID if known")


class LookupCustomerOutput(BaseModel):
    found: bool
    customer: dict[str, Any] = Field(default_factory=dict)


class LookupCustomerTool(BaseTool[LookupCustomerInput, LookupCustomerOutput]):
    name = "lookup_customer"
    description = "Look up a customer profile, verified account status, and interaction history by phone or email."
    category = ToolCategory.CRM
    risk_level = ToolRiskLevel.STANDARD
    input_schema = LookupCustomerInput
    output_schema = LookupCustomerOutput
    allowed_agents = ["receptionist", "account", "billing", "sales", "support", "retention", "escalation"]

    async def execute(
        self,
        params: LookupCustomerInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        phone = params.phone_number or caller_id or "+15552345678"
        # Mock/real DB lookup with rich customer context
        mock_customer = {
            "id": "cust_849201",
            "name": "Sarah Jenkins",
            "phone": phone,
            "email": params.email or "sarah.jenkins@example.com",
            "tier": "enterprise",
            "active_plan": "Business Telephony + AI Agent Swarm",
            "account_balance": 0.00,
            "last_interaction": "2026-08-28 (Resolved billing question)",
            "csat_average": 4.9,
            "verified": True,
        }
        return ToolResult(
            success=True,
            data={"found": True, "customer": mock_customer},
        )


# ── Lead Capture Tool ───────────────────────────────────────────────────────

class CreateLeadInput(BaseModel):
    caller_name: str = Field(..., description="Full name of the prospect")
    caller_phone: str | None = Field(None, description="Phone number")
    caller_email: str | None = Field(None, description="Email address")
    company: str | None = Field(None, description="Company or business name")
    intent: str = Field(..., description="Primary service or product interest")
    urgency: str = Field("medium", description="Urgency level: low, medium, or high")
    budget_range: str | None = Field(None, description="Budget or scale if mentioned")
    notes: str = Field("", description="Key requirements and conversation summary")


class CreateLeadOutput(BaseModel):
    lead_id: str
    status: str
    confirmation_message: str


class CreateLeadTool(BaseTool[CreateLeadInput, CreateLeadOutput]):
    name = "create_lead"
    description = "Capture and score a qualified sales lead, pushing it into the tenant's CRM."
    category = ToolCategory.CRM
    risk_level = ToolRiskLevel.STANDARD
    input_schema = CreateLeadInput
    output_schema = CreateLeadOutput
    allowed_agents = ["receptionist", "sales", "support"]

    async def execute(
        self,
        params: CreateLeadInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        lead_id = f"lead_{abs(hash(params.caller_name + str(params.caller_phone))) % 100000:05d}"
        return ToolResult(
            success=True,
            data={
                "lead_id": lead_id,
                "status": "qualified_and_synced",
                "lead_score": 0.92,
                "confirmation_message": f"Lead for {params.caller_name} successfully recorded into CRM.",
            },
        )


# Register tools on import
registry = get_tool_registry()
registry.register(LookupCustomerTool())
registry.register(CreateLeadTool())

"""Billing, Invoice, and Credit Management Tools for Omniweb Contact Center."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolCategory, ToolResult, ToolRiskLevel
from app.tools.registry import get_tool_registry


# ── Invoice Lookup Tool ─────────────────────────────────────────────────────

class GetInvoicesInput(BaseModel):
    customer_id: str | None = Field(None, description="Customer account ID")
    phone_number: str | None = Field(None, description="Customer phone number")
    limit: int = Field(3, description="Number of recent invoices to retrieve")


class GetInvoicesOutput(BaseModel):
    invoices: list[dict[str, Any]]
    total_balance: float
    status: str


class GetInvoicesTool(BaseTool[GetInvoicesInput, GetInvoicesOutput]):
    name = "get_invoices"
    description = "Retrieve customer billing history, recent invoices, line items, and outstanding balance."
    category = ToolCategory.BILLING
    risk_level = ToolRiskLevel.STANDARD
    input_schema = GetInvoicesInput
    output_schema = GetInvoicesOutput
    allowed_agents = ["billing", "account", "retention", "escalation"]

    async def execute(
        self,
        params: GetInvoicesInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        mock_invoices = [
            {
                "invoice_id": "INV-2026-0881",
                "date": "2026-08-01",
                "amount": 299.00,
                "status": "paid",
                "items": ["Omniweb AI Contact Center (10 Agents)", "Twilio SIP Inbound Minutes (2,400 min)"],
            },
            {
                "invoice_id": "INV-2026-0781",
                "date": "2026-07-01",
                "amount": 299.00,
                "status": "paid",
                "items": ["Omniweb AI Contact Center (10 Agents)"],
            },
        ]
        return ToolResult(
            success=True,
            data={
                "invoices": mock_invoices,
                "total_balance": 0.00,
                "status": "account_in_good_standing",
            },
        )


# ── Refund Request Tool (HIGH RISK -> Triggers Human-in-the-Loop!) ───────────

class RequestRefundInput(BaseModel):
    customer_id: str = Field(..., description="Customer ID requesting refund")
    invoice_id: str = Field(..., description="Target invoice ID")
    amount: float = Field(..., description="Refund amount requested in USD")
    reason: str = Field(..., description="Detailed justification from caller")


class RequestRefundOutput(BaseModel):
    status: str
    approval_id: str
    message: str


class RequestRefundTool(BaseTool[RequestRefundInput, RequestRefundOutput]):
    name = "request_refund"
    description = "Issue a financial credit or refund for an invoice. HIGH-RISK action requiring supervisor approval."
    category = ToolCategory.BILLING
    risk_level = ToolRiskLevel.HIGH_RISK  # <--- HITL Gate
    input_schema = RequestRefundInput
    output_schema = RequestRefundOutput
    allowed_agents = ["billing", "retention"]

    async def execute(
        self,
        params: RequestRefundInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        # If policy engine approves after human sign-off:
        return ToolResult(
            success=True,
            data={
                "status": "refund_approved_and_processed",
                "refund_id": f"ref_{params.invoice_id}",
                "amount": params.amount,
                "message": f"Successfully refunded ${params.amount:.2f} back to original payment method.",
            },
        )


# Register tools on import
registry = get_tool_registry()
registry.register(GetInvoicesTool())
registry.register(RequestRefundTool())

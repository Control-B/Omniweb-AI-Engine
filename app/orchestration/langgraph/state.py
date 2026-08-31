"""Typed State Schema for LangGraph Contact Center Orchestration.

Defines:
- ContactCenterState (TypedDict for LangGraph state machine)
- Pydantic models for boundary validation
- Message & entity structures
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, TypedDict
import uuid

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── TypedDict for LangGraph State Machine ───────────────────────────────────

class ContactCenterState(TypedDict):
    """Core durable state machine representation of a contact center session."""

    tenant_id: str
    session_id: str
    interaction_id: str
    channel: Literal["phone_inbound", "phone_outbound", "browser_voice", "web_chat", "sms", "whatsapp"]

    # Customer Identity & Security
    customer_id: str | None
    caller_phone: str | None
    caller_email: str | None
    identity_verified: bool
    authentication_level: Literal["anonymous", "caller_id_verified", "mfa_authenticated"]

    # Classification & Intent
    language: str
    intent: str | None
    secondary_intents: list[str]
    sentiment: Literal["delighted", "positive", "neutral", "frustrated", "angry"] | None
    urgency: Literal["low", "medium", "high", "critical"] | None
    risk_level: Literal["standard", "high_risk", "critical"]

    # Agent Swarm Execution
    active_agent: str
    previous_agents: list[str]
    workflow_name: str | None
    workflow_step: str | None

    # Context & Entities
    conversation_summary: str
    messages: list[dict[str, Any]]
    entities: dict[str, Any]
    account_context: dict[str, Any]
    customer_context: dict[str, Any]

    # Action & Policy Governance
    requested_actions: list[dict[str, Any]]
    completed_actions: list[dict[str, Any]]
    pending_actions: list[dict[str, Any]]
    approval_required: bool
    approval_status: Literal["pending", "approved", "rejected", "expired"] | None
    approval_id: str | None

    # Escalation
    escalation_required: bool
    escalation_reason: str | None

    # Audit & Tool Tracing
    tool_calls: list[dict[str, Any]]
    tool_results: dict[str, Any]
    errors: list[dict[str, Any]]

    # Response & Audio Output
    response_text: str | None
    suggested_actions: list[dict[str, Any]]

    started_at: str
    updated_at: str


# ── Factory Helper to initialize a new session state ────────────────────────

def create_initial_state(
    *,
    tenant_id: str,
    session_id: str | None = None,
    channel: Literal["phone_inbound", "phone_outbound", "browser_voice", "web_chat", "sms", "whatsapp"] = "browser_voice",
    caller_phone: str | None = None,
    caller_email: str | None = None,
    customer_id: str | None = None,
    initial_message: str | None = None,
) -> ContactCenterState:
    """Factory helper to construct an initial ContactCenterState instance."""
    now = utcnow()
    sess_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    interaction_id = f"int_{uuid.uuid4().hex[:12]}"

    messages: list[dict[str, Any]] = []
    if initial_message:
        messages.append({
            "role": "user",
            "content": initial_message,
            "timestamp": now,
        })

    return {
        "tenant_id": tenant_id,
        "session_id": sess_id,
        "interaction_id": interaction_id,
        "channel": channel,
        "customer_id": customer_id,
        "caller_phone": caller_phone,
        "caller_email": caller_email,
        "identity_verified": bool(customer_id),
        "authentication_level": "caller_id_verified" if caller_phone else "anonymous",
        "language": "en",
        "intent": None,
        "secondary_intents": [],
        "sentiment": "neutral",
        "urgency": "medium",
        "risk_level": "standard",
        "active_agent": "receptionist",
        "previous_agents": [],
        "workflow_name": "general_inquiry",
        "workflow_step": "init",
        "conversation_summary": "",
        "messages": messages,
        "entities": {},
        "account_context": {},
        "customer_context": {},
        "requested_actions": [],
        "completed_actions": [],
        "pending_actions": [],
        "approval_required": False,
        "approval_status": None,
        "approval_id": None,
        "escalation_required": False,
        "escalation_reason": None,
        "tool_calls": [],
        "tool_results": {},
        "errors": [],
        "response_text": None,
        "suggested_actions": [],
        "started_at": now,
        "updated_at": now,
    }

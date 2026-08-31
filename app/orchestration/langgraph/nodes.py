"""State Machine Nodes for LangGraph Contact Center Orchestration."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.telemetry import MetricTracker, correlation_scope
from app.orchestration.langgraph.state import ContactCenterState, utcnow
from app.orchestration.model_router import ModelTier, get_model_router
from app.tools.registry import get_tool_registry

logger = get_logger(__name__)
model_router = get_model_router()
tool_registry = get_tool_registry()


# ── 1. Intent & Context Classification Node ─────────────────────────────────

class NLUClassification(BaseModel):
    intent: str = Field(..., description="Primary intent: billing_inquiry, appointment_booking, sales_inquiry, technical_issue, cancel_subscription, human_escalation, general_inquiry")
    secondary_intents: list[str] = Field(default_factory=list)
    language: str = Field("en", description="Detected language code (en, es, fr, etc.)")
    sentiment: str = Field("neutral", description="delighted, positive, neutral, frustrated, angry")
    urgency: str = Field("medium", description="low, medium, high, critical")
    extracted_entities: dict[str, Any] = Field(default_factory=dict, description="Extracted dates, names, amounts, invoice numbers")


async def classifier_node(state: ContactCenterState) -> dict[str, Any]:
    """Classify caller intent, sentiment, language, and extract key business entities."""
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "general_inquiry", "updated_at": utcnow()}

    last_user_message = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )

    prompt = f"""Analyze this customer message in an AI contact center conversation:
Customer Message: "{last_user_message}"
Existing Context: {json.dumps(state.get('entities', {}))}

Classify intent into one of:
- billing_inquiry (bills, invoices, payment, charges)
- appointment_booking (scheduling, calendar, meetings)
- sales_inquiry (pricing, packages, buying, upgrades)
- technical_issue (diagnostics, troubleshooting, outages, errors)
- cancel_subscription (retention risk, cancellation request)
- human_escalation (asking for manager/human, severe frustration)
- general_inquiry (hours, services, greetings, company questions)
"""

    classification = await model_router.generate_structured(
        prompt=prompt,
        schema=NLUClassification,
        tier=ModelTier.FAST_INTENT,
    )

    merged_entities = {**state.get("entities", {}), **classification.extracted_entities}

    # Detect high risk
    risk_level = "high_risk" if classification.intent in ("cancel_subscription", "refund_request") or classification.urgency == "critical" else "standard"

    logger.info(
        f"[Classifier Node] Intent={classification.intent}, Sentiment={classification.sentiment}, Urgency={classification.urgency}"
    )

    return {
        "intent": classification.intent,
        "secondary_intents": classification.secondary_intents,
        "language": classification.language,
        "sentiment": classification.sentiment,
        "urgency": classification.urgency,
        "risk_level": risk_level,
        "entities": merged_entities,
        "updated_at": utcnow(),
    }


# ── 2. Supervisor / Router Node ─────────────────────────────────────────────

async def router_node(state: ContactCenterState) -> dict[str, Any]:
    """Route conversation to the appropriate specialist agent based on intent & risk."""
    intent = state.get("intent") or "general_inquiry"
    current_agent = state.get("active_agent") or "receptionist"
    urgency = state.get("urgency") or "medium"
    sentiment = state.get("sentiment") or "neutral"

    # Escalation condition
    if intent == "human_escalation" or sentiment == "angry" or urgency == "critical":
        next_agent = "escalation"
        workflow_name = "human_escalation"
    elif intent == "billing_inquiry":
        next_agent = "billing"
        workflow_name = "billing_inquiry"
    elif intent == "appointment_booking":
        next_agent = "scheduling"
        workflow_name = "appointment_booking"
    elif intent == "sales_inquiry":
        next_agent = "sales"
        workflow_name = "sales_conversion"
    elif intent == "technical_issue":
        next_agent = "support"
        workflow_name = "technical_troubleshooting"
    elif intent == "cancel_subscription":
        next_agent = "retention"
        workflow_name = "retention_workflow"
    else:
        next_agent = "receptionist"
        workflow_name = "general_inquiry"

    previous_agents = state.get("previous_agents", [])
    if current_agent != next_agent and current_agent not in previous_agents:
        previous_agents = [*previous_agents, current_agent]

    logger.info(f"[Router Node] Routing from [{current_agent}] -> [{next_agent}] (Workflow: {workflow_name})")

    return {
        "active_agent": next_agent,
        "previous_agents": previous_agents,
        "workflow_name": workflow_name,
        "updated_at": utcnow(),
    }


# ── 3. Specialist Agent Execution Node ──────────────────────────────────────

AGENT_PROFILES: dict[str, dict[str, Any]] = {
    "receptionist": {
        "role": "You are the AI Front Desk Receptionist for Omniweb Contact Center.",
        "instructions": "Warmly greet the caller, understand their reason for reaching out, provide helpful company information, and collect their contact details.",
        "tools": ["lookup_customer", "create_lead", "search_knowledge", "check_availability"],
    },
    "account": {
        "role": "You are the Customer Account Specialist.",
        "instructions": "Help the customer verify their identity, review account settings, and inspect service status with care.",
        "tools": ["lookup_customer", "search_knowledge"],
    },
    "billing": {
        "role": "You are the Billing & Invoicing Specialist.",
        "instructions": "Assist callers with recent invoice reviews, balance inquiries, payment links, and billing explanations. For refund requests, explain policy clearly and invoke request_refund.",
        "tools": ["lookup_customer", "get_invoices", "request_refund", "search_knowledge"],
    },
    "sales": {
        "role": "You are the Enterprise Sales & Solutions Specialist.",
        "instructions": "Qualify prospects by understanding their team size, call volume, and automation goals. Propose the optimal Omniweb package and schedule a live walkthrough.",
        "tools": ["lookup_customer", "create_lead", "check_availability", "book_appointment", "search_knowledge"],
    },
    "support": {
        "role": "You are the Tier-1 Technical Support & Diagnostics Specialist.",
        "instructions": "Guide callers through troubleshooting steps for voice widgets, SIP routing, or dashboard setup. If unresolved, create a tracked support ticket.",
        "tools": ["lookup_customer", "search_knowledge", "create_ticket", "check_availability"],
    },
    "scheduling": {
        "role": "You are the Executive Scheduling Assistant.",
        "instructions": "Coordinate calendar bookings seamlessly. Check available time slots, confirm attendee details, and book the meeting.",
        "tools": ["check_availability", "book_appointment", "search_knowledge"],
    },
    "retention": {
        "role": "You are the Customer Retention & Value Advisor.",
        "instructions": "Listen empathetically to cancellation reasons, reiterate account value, and offer approved retention credits before executing cancellation.",
        "tools": ["lookup_customer", "get_invoices", "request_refund", "search_knowledge"],
    },
    "site_concierge": {
        "role": "You are the Omniweb Site Concierge & Navigation Specialist.",
        "instructions": "Help website visitors discover platform capabilities, understand our autonomous voice & chat agent services, explore pricing tiers ($49/$149/Enterprise), and navigate to exact pages on the site using the navigate_site tool.",
        "tools": ["navigate_site", "search_knowledge", "lookup_customer", "check_availability", "create_lead"],
    },
    "escalation": {
        "role": "You are the Human Escalation Coordinator.",
        "instructions": "Reassure the caller that a senior human specialist is being connected immediately. Summarize their inquiry accurately so they will not need to repeat themselves.",
        "tools": ["lookup_customer", "create_ticket"],
    },
}


async def specialist_agent_node(state: ContactCenterState) -> dict[str, Any]:
    """Execute the designated specialist agent logic and generate response/tool calls."""
    active_agent = state.get("active_agent") or "receptionist"
    profile = AGENT_PROFILES.get(active_agent, AGENT_PROFILES["receptionist"])
    messages = state.get("messages", [])
    last_user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "Hello")

    available_tools = tool_registry.get_tools_for_agent(active_agent)
    tool_schemas = [t.get_json_schema() for t in available_tools]

    system_instruction = f"""{profile['role']}
{profile['instructions']}

Operating Guidelines:
1. Speak concisely, professionally, and naturally.
2. When the visitor asks where to find something, questions about pricing, features, or solutions, call navigate_site and search_knowledge.
3. Customer Profile: {json.dumps(state.get('customer_context', {}))}
4. Extracted Entities: {json.dumps(state.get('entities', {}))}
"""

    prompt = f"""Customer: "{last_user_msg}"
Active Workflow: {state.get('workflow_name')}
Previous Turns: {len(messages)}
"""

    # Decide if a tool call is needed based on intent and entities
    tool_calls: list[dict[str, Any]] = []
    intent = state.get("intent")
    user_lower = last_user_msg.lower()

    if any(nav_word in user_lower for nav_word in ["where", "how much", "price", "pricing", "feature", "solution", "shopify", "demo", "doc", "api", "page", "take me", "navigate", "services"]):
        tool_calls.append({"name": "navigate_site", "parameters": {"query": last_user_msg}})

    if intent == "billing_inquiry" and active_agent == "billing" and not state.get("tool_results", {}).get("get_invoices"):
        tool_calls.append({"name": "get_invoices", "parameters": {"limit": 2}})
    elif intent == "appointment_booking" and active_agent == "scheduling" and not state.get("tool_results", {}).get("check_availability"):
        tool_calls.append({"name": "check_availability", "parameters": {"date_str": "tomorrow"}})
    elif not state.get("tool_results", {}).get("search_knowledge"):
        tool_calls.append({"name": "search_knowledge", "parameters": {"query": last_user_msg}})

    model_resp = await model_router.generate_text(
        prompt=prompt,
        system_instruction=system_instruction,
        tier=ModelTier.PRIMARY_CONVERSATION,
    )

    return {
        "response_text": model_resp.content,
        "tool_calls": tool_calls,
        "updated_at": utcnow(),
    }


# ── 4. Tool Execution Node ──────────────────────────────────────────────────

async def tool_execution_node(state: ContactCenterState) -> dict[str, Any]:
    """Execute all pending tool calls and record results into state."""
    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return {"updated_at": utcnow()}

    active_agent = state.get("active_agent") or "receptionist"
    tenant_id = state.get("tenant_id") or "tenant_default"
    caller_id = state.get("caller_phone")

    results = {**state.get("tool_results", {})}
    completed_actions = [*state.get("completed_actions", [])]
    pending_actions = [*state.get("pending_actions", [])]
    approval_required = False
    approval_id = None

    for call in tool_calls:
        tool_name = call.get("name")
        params = call.get("parameters", {})
        if not tool_name:
            continue

        res = await tool_registry.execute_tool(
            tool_name,
            params,
            tenant_id=tenant_id,
            agent_name=active_agent,
            caller_id=caller_id,
            context=state.get("entities"),
        )

        results[tool_name] = res.data
        if res.requires_approval:
            approval_required = True
            approval_id = res.approval_id
            pending_actions.append({"tool": tool_name, "approval_id": approval_id, "params": params})
        else:
            completed_actions.append({"tool": tool_name, "result": res.data})

    return {
        "tool_results": results,
        "completed_actions": completed_actions,
        "pending_actions": pending_actions,
        "approval_required": approval_required,
        "approval_id": approval_id,
        "tool_calls": [],  # clear executed calls
        "updated_at": utcnow(),
    }


# ── 5. Finalizer Node ───────────────────────────────────────────────────────

async def finalizer_node(state: ContactCenterState) -> dict[str, Any]:
    """Assemble final response text, update conversation history, and finalize turn."""
    response_text = state.get("response_text") or "I am here to assist you. How can I help further?"
    messages = [*state.get("messages", [])]
    active_agent = state.get("active_agent") or "receptionist"

    # Append assistant turn
    messages.append({
        "role": "assistant",
        "agent": active_agent,
        "content": response_text,
        "timestamp": utcnow(),
    })

    summary = f"Customer inquired about {state.get('intent')}. Handled by {active_agent}."

    return {
        "messages": messages,
        "conversation_summary": summary,
        "response_text": response_text,
        "updated_at": utcnow(),
    }

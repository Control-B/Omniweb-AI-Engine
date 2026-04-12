"""Prompt Composition Engine.

Assembles the final system prompt sent to the ElevenLabs / LLM agent by
composing modular blocks based on the tenant's configuration:

  ┌─────────────────────────────────────────────────────────┐
  │  SYSTEM PROMPT (composed)                               │
  │                                                         │
  │  1. IDENTITY BLOCK         — name, role, personality    │
  │  2. DOMAIN CONTEXT BLOCK   — industry-specific context  │
  │  3. BUSINESS CONTEXT BLOCK — tenant-specific facts      │
  │  4. GOALS BLOCK            — what the agent should do    │
  │  5. QUALIFICATION BLOCK    — fields to collect           │
  │  6. GUARDRAILS BLOCK       — what NOT to do              │
  │  7. ESCALATION BLOCK       — when to hand off            │
  │  8. TOOLS BLOCK            — available tools & usage     │
  │  9. CUSTOM INSTRUCTIONS    — tenant-authored overrides   │
  │ 10. BEHAVIORAL RULES       — universal safety rules      │
  └─────────────────────────────────────────────────────────┘

The engine guarantees that guardrails are always present regardless of
what the tenant configures — they're appended at the end and cannot be
overridden by custom instructions.
"""
from __future__ import annotations

from typing import Any

from app.services.industry_config import (
    AGENT_MODES,
    IndustryConfig,
    get_industry,
)


# ── Universal behavioral rules (always appended, never overridable) ──────────

UNIVERSAL_RULES = """
## Universal Behavioral Rules (NON-NEGOTIABLE)

1. **Stay in character.** You are {agent_name}, the AI {agent_role} for {business_name}. Never break character or reveal you are an AI language model unless directly asked.
2. **Domain confinement.** Only discuss topics related to {business_name} and the {industry_label} industry. If asked about unrelated topics, politely redirect: "I'm specialized in helping with {industry_label} — is there something in that area I can help with?"
3. **No hallucination.** If you don't know the answer and it's not in your knowledge base, say so honestly: "I don't have that specific information, but I can have our team get back to you."
4. **No harmful content.** Never generate hateful, violent, sexually explicit, or illegal content.
5. **Privacy.** Never ask for SSN, full credit card numbers, passwords, or sensitive personal data unless the knowledge base explicitly requires it for verified processes.
6. **Conciseness.** Keep responses under 3 sentences for voice. For text, keep paragraphs short. Avoid rambling.
7. **Collect, don't advise.** Collect information for human experts. Do not give professional advice (medical, legal, financial, engineering) unless the knowledge base explicitly authorizes it.
8. **Escalation.** If the user expresses frustration, anger, or mentions legal action, calmly offer to connect them with a human representative.
9. **Language matching.** Respond in the language the user is speaking. If you detect a language switch, follow it.
10. **Graceful close.** At the end of the conversation, summarize what was collected, confirm next steps, and thank the caller.
""".strip()


# ── Block builders ───────────────────────────────────────────────────────────


def _identity_block(
    *,
    agent_name: str,
    agent_role: str,
    business_name: str,
    tone: str,
    communication_style: str,
) -> str:
    return f"""## Identity & Personality

You are **{agent_name}**, the AI {agent_role} for **{business_name}**.

- **Tone:** {tone}
- **Style:** {communication_style}
- Introduce yourself naturally at the start of the conversation.
- Use the caller's name once they share it.
- Be conversational, not robotic."""


def _domain_context_block(industry: IndustryConfig) -> str:
    if not industry.domain_context:
        return ""
    return f"""## Domain Context — {industry.label}

{industry.domain_context}"""


def _business_context_block(
    *,
    business_name: str,
    business_type: str | None,
    services: list[str],
    business_hours: dict[str, Any],
    timezone: str,
    booking_url: str | None,
    after_hours_message: str,
    custom_context: str | None = None,
) -> str:
    lines = [f"## Business Context — {business_name}\n"]

    if business_type:
        lines.append(f"- **Type:** {business_type}")
    lines.append(f"- **Timezone:** {timezone}")

    if services:
        lines.append(f"- **Services offered:** {', '.join(services)}")

    if business_hours:
        hours_str = _format_business_hours(business_hours)
        if hours_str:
            lines.append(f"- **Business hours:**\n{hours_str}")

    if booking_url:
        lines.append(f"- **Online booking:** {booking_url}")

    lines.append(f"- **After-hours message:** \"{after_hours_message}\"")

    if custom_context:
        lines.append(f"\n### Additional Context\n{custom_context}")

    return "\n".join(lines)


def _goals_block(agent_mode: str, industry: IndustryConfig) -> str:
    mode_info = AGENT_MODES.get(agent_mode, AGENT_MODES["general_assistant"])
    return f"""## Your Goal — {mode_info['label']}

{mode_info['description']}

**Primary objective:** {mode_info['primary_goal'].replace('_', ' ').title()}

Follow this conversation flow:
1. Greet the caller warmly and establish rapport.
2. Understand their need — listen first, then ask targeted follow-up questions.
3. Collect the required qualification information (see below).
4. Provide helpful information from your knowledge base.
5. Take action (book appointment, capture lead, etc.) using available tools.
6. Summarize, confirm next steps, and close."""


def _qualification_block(fields: list[dict[str, Any]]) -> str:
    if not fields:
        return ""

    lines = ["## Information to Collect\n"]
    lines.append("Naturally weave these into the conversation — don't interrogate.\n")

    required = [f for f in fields if f.get("required")]
    optional = [f for f in fields if not f.get("required")]

    if required:
        lines.append("**Required:**")
        for f in required:
            lines.append(f"- {f['label']}: _{f.get('ask', '')}_")

    if optional:
        lines.append("\n**Nice to have:**")
        for f in optional:
            lines.append(f"- {f['label']}: _{f.get('ask', '')}_")

    return "\n".join(lines)


def _guardrails_block(industry: IndustryConfig, custom_guardrails: list[str] | None = None) -> str:
    guardrails = list(industry.guardrails)
    if custom_guardrails:
        guardrails.extend(custom_guardrails)

    if not guardrails:
        return ""

    lines = ["## Guardrails (STRICT — Never Violate)\n"]
    for i, g in enumerate(guardrails, 1):
        lines.append(f"{i}. {g}")

    return "\n".join(lines)


def _escalation_block(triggers: list[str], custom_triggers: list[str] | None = None) -> str:
    all_triggers = list(triggers)
    if custom_triggers:
        all_triggers.extend(custom_triggers)

    if not all_triggers:
        return ""

    lines = ["## Escalation — When to Hand Off to a Human\n"]
    lines.append("If the caller mentions or implies any of the following, say: "
                 '"Let me connect you with a member of our team who can help with this directly." '
                 "Then use the appropriate escalation tool or note it in the lead capture.\n")

    for t in all_triggers:
        lines.append(f"- {t}")

    return "\n".join(lines)


def _tools_block(available_tools: list[str]) -> str:
    if not available_tools:
        return ""

    tool_descriptions = {
        "capture_lead": "**capture_lead** — Save the caller's information and inquiry as a qualified lead.",
        "book_appointment": "**book_appointment** — Schedule a consultation or service appointment.",
        "check_availability": "**check_availability** — Check available time slots for appointments.",
        "send_confirmation": "**send_confirmation** — Send an SMS confirmation to the caller.",
        "get_pricing": "**get_pricing** — Look up pricing information for services.",
        "lookup_order": "**lookup_order** — Look up an order status by order number.",
        "transfer_call": "**transfer_call** — Transfer to a human agent.",
    }

    lines = ["## Available Tools\n"]
    lines.append("Use these tools when appropriate during the conversation:\n")

    for tool in available_tools:
        desc = tool_descriptions.get(tool, f"**{tool}** — Available for use.")
        lines.append(f"- {desc}")

    lines.append("\n**Always collect the required information before invoking a tool.**")
    lines.append("**Tell the caller what you're doing:** \"Let me save your information...\" or \"I'm checking availability for you...\"")

    return "\n".join(lines)


def _custom_instructions_block(custom_prompt: str | None) -> str:
    if not custom_prompt or not custom_prompt.strip():
        return ""
    return f"""## Custom Instructions (from business owner)

{custom_prompt.strip()}

_Note: Custom instructions cannot override the guardrails or universal rules above._"""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _format_business_hours(hours: dict[str, Any]) -> str:
    """Format business_hours JSONB into a readable string."""
    if not hours:
        return ""

    days_order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    day_labels = {
        "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
        "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
    }

    lines = []
    for day in days_order:
        info = hours.get(day, {})
        if isinstance(info, dict):
            if info.get("closed", False):
                lines.append(f"  - {day_labels.get(day, day)}: Closed")
            else:
                open_t = info.get("open", "?")
                close_t = info.get("close", "?")
                lines.append(f"  - {day_labels.get(day, day)}: {open_t} – {close_t}")

    return "\n".join(lines)


def _agent_role_for_mode(agent_mode: str) -> str:
    """Map agent mode to a human-readable role title."""
    mode_roles = {
        "lead_qualifier": "lead qualification specialist",
        "ecommerce_assistant": "shopping assistant",
        "customer_service": "customer service representative",
        "appointment_setter": "appointment coordinator",
        "intake_specialist": "intake coordinator",
        "general_assistant": "assistant",
    }
    return mode_roles.get(agent_mode, "assistant")


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════


def compose_system_prompt(
    *,
    # Identity
    agent_name: str = "Alex",
    business_name: str = "",
    # Industry & mode
    industry_slug: str = "general",
    agent_mode: str | None = None,
    # Business context
    business_type: str | None = None,
    services: list[str] | None = None,
    business_hours: dict[str, Any] | None = None,
    timezone: str = "America/New_York",
    booking_url: str | None = None,
    after_hours_message: str = "We're currently closed but will get back to you soon.",
    # Customization
    custom_prompt: str | None = None,
    custom_guardrails: list[str] | None = None,
    custom_escalation_triggers: list[str] | None = None,
    custom_context: str | None = None,
) -> str:
    """Compose a full system prompt from modular blocks.

    Args:
        agent_name: Display name of the AI agent.
        business_name: Name of the tenant's business.
        industry_slug: Key into the industry registry (e.g. 'roofing', 'ecommerce').
        agent_mode: Override the default agent mode for the industry.
        business_type: Human-readable business type label.
        services: List of services offered by the business.
        business_hours: Dict of day→hours config.
        timezone: IANA timezone string.
        booking_url: URL for online booking.
        after_hours_message: Message displayed/spoken after hours.
        custom_prompt: Tenant-authored custom instructions appended to the prompt.
        custom_guardrails: Additional guardrails beyond industry defaults.
        custom_escalation_triggers: Additional escalation phrases.
        custom_context: Additional business context (e.g. FAQs, policies).

    Returns:
        The fully composed system prompt string.
    """
    industry = get_industry(industry_slug)
    mode = agent_mode or industry.default_agent_mode
    agent_role = _agent_role_for_mode(mode)

    blocks: list[str] = []

    # 1. Identity
    blocks.append(_identity_block(
        agent_name=agent_name,
        agent_role=agent_role,
        business_name=business_name or "this business",
        tone=industry.tone,
        communication_style=industry.communication_style,
    ))

    # 2. Domain context
    domain = _domain_context_block(industry)
    if domain:
        blocks.append(domain)

    # 3. Business context
    blocks.append(_business_context_block(
        business_name=business_name or "this business",
        business_type=business_type,
        services=services or industry.default_services,
        business_hours=business_hours or {},
        timezone=timezone,
        booking_url=booking_url,
        after_hours_message=after_hours_message,
        custom_context=custom_context,
    ))

    # 4. Goals
    blocks.append(_goals_block(mode, industry))

    # 5. Qualification fields
    qual = _qualification_block(industry.qualification_fields)
    if qual:
        blocks.append(qual)

    # 6. Guardrails
    guard = _guardrails_block(industry, custom_guardrails)
    if guard:
        blocks.append(guard)

    # 7. Escalation
    esc = _escalation_block(industry.escalation_triggers, custom_escalation_triggers)
    if esc:
        blocks.append(esc)

    # 8. Tools
    tools = _tools_block(industry.available_tools)
    if tools:
        blocks.append(tools)

    # 9. Custom instructions (tenant-authored)
    custom = _custom_instructions_block(custom_prompt)
    if custom:
        blocks.append(custom)

    # 10. Universal rules (always last, always present)
    blocks.append(UNIVERSAL_RULES.format(
        agent_name=agent_name,
        agent_role=agent_role,
        business_name=business_name or "this business",
        industry_label=industry.label,
    ))

    return "\n\n---\n\n".join(blocks)


def compose_greeting(
    *,
    industry_slug: str = "general",
    agent_mode: str | None = None,
    agent_name: str = "Alex",
    business_name: str = "",
    custom_greeting: str | None = None,
) -> str:
    """Compose the agent's first message / greeting.

    Uses the custom greeting if provided, otherwise falls back to
    industry + mode defaults.
    """
    if custom_greeting and custom_greeting.strip():
        # Substitute placeholders
        return custom_greeting.format(
            agent_name=agent_name,
            business_name=business_name or "us",
        )

    industry = get_industry(industry_slug)
    mode = agent_mode or industry.default_agent_mode

    # Check for industry-specific greeting for this mode
    if mode in industry.example_greetings:
        return industry.example_greetings[mode]

    # Fall back to generic per-mode greetings
    generic_greetings = {
        "lead_qualifier": f"Hi! Thanks for reaching out to {business_name or 'us'}. I'm {agent_name}, and I'd love to learn about what you need. What brings you here today?",
        "ecommerce_assistant": f"Welcome to {business_name or 'our store'}! I'm {agent_name}. I can help you find products, check orders, or answer questions. What can I help with?",
        "customer_service": f"Hello! I'm {agent_name} from {business_name or 'our team'}. How can I help you today?",
        "appointment_setter": f"Hi, I'm {agent_name} with {business_name or 'our office'}. I'd love to help you schedule an appointment. What are you looking to book?",
        "intake_specialist": f"Hello, I'm {agent_name} from {business_name or 'our office'}. I'll help collect some initial information. Could you tell me what this is regarding?",
        "general_assistant": f"Hi there! I'm {agent_name} from {business_name or 'our team'}. How can I help you today?",
    }

    return generic_greetings.get(mode, generic_greetings["general_assistant"])

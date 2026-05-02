"""Tool Registry — maps logical tool names to Retell-compatible webhook tools.

Industry configs reference tool names; this registry resolves them to HTTP
tool definitions (URL, schema, shared secret header).

When a tenant's agent is created/updated, the prompt engine + tool registry
together determine which tools the agent should have access to.
"""
from __future__ import annotations

from typing import Any

from app.core.config import get_settings

settings = get_settings()


# ── Tool Definition Schema ───────────────────────────────────────────────────

def _base_url() -> str:
    """Return the platform's base URL for tool webhook callbacks."""
    return settings.APP_BASE_URL.rstrip("/")


# Each tool definition follows a JSON-schema style compatible with Retell custom tools:
# {
#   "type": "webhook",
#   "name": "tool_name",
#   "description": "What the tool does (agent reads this to decide when to use it)",
#   "api_schema": {
#     "url": "https://...",
#     "method": "POST",
#     "headers": {"X-Tool-Secret": "..."},
#     "request_body": {
#       "type": "object",
#       "properties": {...},
#       "required": [...]
#     }
#   }
# }


TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {

    "capture_lead": {
        "type": "webhook",
        "name": "capture_lead",
        "description": (
            "Save the caller's contact information and inquiry as a qualified lead. "
            "Use this tool once you've collected their name and understood their need. "
            "This stores the lead for follow-up by the business team."
        ),
        "api_schema": {
            "url": "{base_url}/api/tools/capture-lead",
            "method": "POST",
            "headers": {"X-Tool-Secret": "{tool_secret}"},
            "request_body": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name of the lead"},
                    "email": {"type": "string", "description": "Email address (if provided)"},
                    "phone": {"type": "string", "description": "Phone number (if provided)"},
                    "business_name": {"type": "string", "description": "Lead's business name (if applicable)"},
                    "industry": {"type": "string", "description": "Lead's industry or business type"},
                    "challenge": {"type": "string", "description": "Main pain point or challenge described"},
                    "services_interested": {"type": "string", "description": "Comma-separated list of services they showed interest in"},
                    "urgency": {"type": "string", "description": "low, medium, or high"},
                    "notes": {"type": "string", "description": "Additional context from the conversation"},
                },
                "required": ["name"],
            },
        },
    },

    "book_appointment": {
        "type": "webhook",
        "name": "book_appointment",
        "description": (
            "Schedule an appointment or consultation. Use this when the caller wants to "
            "book a specific time. First use check_availability, then collect their name, "
            "email, and confirmed ISO start_time before calling this tool."
        ),
        "api_schema": {
            "url": "{base_url}/api/tools/book-appointment",
            "method": "POST",
            "headers": {"X-Tool-Secret": "{tool_secret}"},
            "request_body": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the person booking"},
                    "email": {"type": "string", "description": "Email for calendar invite"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "start_time": {"type": "string", "description": "Confirmed ISO start time from check_availability"},
                    "event_type_id": {"type": "string", "description": "Tenant event type ID, if provided by availability"},
                    "timezone": {"type": "string", "description": "Attendee timezone, e.g. America/New_York"},
                    "preferred_date": {"type": "string", "description": "Preferred date (e.g. 'next Tuesday', '2025-04-15')"},
                    "preferred_time": {"type": "string", "description": "Preferred time (e.g. '2pm', '10:00 AM')"},
                    "topic": {"type": "string", "description": "What they want to discuss"},
                },
                "required": ["name", "email", "start_time"],
            },
        },
    },

    "check_availability": {
        "type": "webhook",
        "name": "check_availability",
        "description": (
            "Check available time slots for appointments. Use this when the caller "
            "asks about available times before booking."
        ),
        "api_schema": {
            "url": "{base_url}/api/tools/check-availability",
            "method": "POST",
            "headers": {"X-Tool-Secret": "{tool_secret}"},
            "request_body": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date to check availability for"},
                    "event_type_id": {"type": "string", "description": "Tenant event type ID, if known"},
                    "timezone": {"type": "string", "description": "Timezone for returned slots"},
                },
                "required": [],
            },
        },
    },

    "send_confirmation": {
        "type": "webhook",
        "name": "send_confirmation",
        "description": (
            "Send an SMS confirmation to the caller. Use this after booking an appointment "
            "or capturing a lead when the caller has provided their phone number."
        ),
        "api_schema": {
            "url": "{base_url}/api/tools/send-confirmation",
            "method": "POST",
            "headers": {"X-Tool-Secret": "{tool_secret}"},
            "request_body": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Phone number (with country code)"},
                    "name": {"type": "string", "description": "Person's name"},
                    "message_type": {"type": "string", "description": "booking, follow_up, or info"},
                    "details": {"type": "string", "description": "Extra details for the message"},
                },
                "required": ["phone", "name"],
            },
        },
    },

    "get_pricing": {
        "type": "webhook",
        "name": "get_pricing",
        "description": (
            "Look up pricing information for services. Use when the caller asks about "
            "costs, pricing, or plans."
        ),
        "api_schema": {
            "url": "{base_url}/api/tools/get-pricing",
            "method": "POST",
            "headers": {"X-Tool-Secret": "{tool_secret}"},
            "request_body": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Which service to get pricing for"},
                },
                "required": [],
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════


def get_tool_definitions(
    tool_names: list[str],
    *,
    base_url: str | None = None,
    tool_secret: str | None = None,
) -> list[dict[str, Any]]:
    """Return resolved custom tool definitions for the given tool names.

    Substitutes {base_url} and {tool_secret} placeholders in URLs and headers.
    """
    resolved_base = base_url or _base_url()
    resolved_secret = tool_secret or settings.TOOL_WEBHOOK_SECRET

    tools: list[dict[str, Any]] = []
    for name in tool_names:
        defn = TOOL_DEFINITIONS.get(name)
        if not defn:
            continue

        # Deep copy and substitute placeholders
        import copy
        tool = copy.deepcopy(defn)
        schema = tool.get("api_schema", {})

        if "url" in schema:
            schema["url"] = schema["url"].format(
                base_url=resolved_base,
                tool_secret=resolved_secret,
            )

        if "headers" in schema:
            schema["headers"] = {
                k: v.format(base_url=resolved_base, tool_secret=resolved_secret)
                for k, v in schema["headers"].items()
            }

        tools.append(tool)

    return tools


def list_available_tools() -> list[dict[str, str]]:
    """Return a summary of all available tools."""
    return [
        {
            "name": name,
            "description": defn.get("description", ""),
        }
        for name, defn in TOOL_DEFINITIONS.items()
    ]


def get_tool_names() -> list[str]:
    """Return all registered tool names."""
    return list(TOOL_DEFINITIONS.keys())

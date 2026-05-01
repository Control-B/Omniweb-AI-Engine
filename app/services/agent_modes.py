from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_AGENT_MODE = "general_lead_gen"
DEFAULT_ENABLED_CHANNELS = ["website_chat"]
DEFAULT_LEAD_CAPTURE_FIELDS = ["name", "email", "phone", "company", "goal"]
DEFAULT_ENABLED_FEATURES = {
    "knowledgeBase": True,
    "leadCapture": True,
    "qualification": True,
    "appointmentBooking": False,
    "liveTransfer": False,
    "smsFollowUp": False,
    "analytics": True,
    "productRecommendations": False,
    "roadsideDispatch": False,
}
DEFAULT_QUALIFICATION_RULES = {
    "requiredFields": ["name", "email"],
    "handoffTriggers": [],
    "disqualifiers": [],
    "conversionSignals": ["pricing", "demo", "quote", "book", "buy"],
}


@dataclass(frozen=True)
class AgentModeDefinition:
    key: str
    label: str
    description: str
    prompt_focus: str
    conversion_objective: str
    default_goals: list[str]
    default_channels: list[str]
    default_lead_capture_fields: list[str]
    default_enabled_features: dict[str, bool]
    qualification_notes: list[str]
    conversion_stages: list[str]


LEAD_CAPTURE_FIELD_OPTIONS: list[dict[str, str]] = [
    {"value": "name", "label": "Name"},
    {"value": "email", "label": "Email"},
    {"value": "phone", "label": "Phone"},
    {"value": "company", "label": "Company"},
    {"value": "goal", "label": "Primary Goal"},
    {"value": "timeline", "label": "Timeline"},
    {"value": "budget", "label": "Budget"},
    {"value": "location", "label": "Location"},
    {"value": "vehicle", "label": "Vehicle"},
    {"value": "serviceType", "label": "Service Type"},
    {"value": "productInterest", "label": "Product Interest"},
    {"value": "orderNumber", "label": "Order Number"},
]

CHANNEL_OPTIONS: list[dict[str, str]] = [
    {"value": "website_chat", "label": "Website chat"},
    {"value": "ai_voice_call", "label": "Voice widget"},
    {"value": "ai_telephony", "label": "Telephony"},
    {"value": "shopify_storefront", "label": "Storefront"},
]

_MODE_REGISTRY: dict[str, AgentModeDefinition] = {
    "ecommerce": AgentModeDefinition(
        key="ecommerce",
        label="Ecommerce revenue agent",
        description="Guides shoppers, recommends products, handles objections, and moves high-intent buyers toward cart or checkout.",
        prompt_focus="Act like a high-performing digital sales associate focused on fit, confidence, and conversion.",
        conversion_objective="Increase add-to-cart rate, average order value, and checkout completion.",
        default_goals=["product_recommendations", "cart_recovery", "upsell_cross_sell", "order_support"],
        default_channels=["website_chat", "shopify_storefront"],
        default_lead_capture_fields=["name", "email", "phone", "productInterest", "timeline"],
        default_enabled_features={
            **DEFAULT_ENABLED_FEATURES,
            "productRecommendations": True,
            "smsFollowUp": True,
        },
        qualification_notes=[
            "Ask one fit question before recommending products.",
            "Use objections to clarify fit, urgency, and confidence barriers.",
            "Capture contact details before escalating returns, refunds, or order exceptions.",
        ],
        conversion_stages=["awareness", "consideration", "intent", "conversion", "retention"],
    ),
    "roadside": AgentModeDefinition(
        key="roadside",
        label="Roadside dispatch agent",
        description="Captures emergency context quickly, triages safely, and routes stranded drivers toward dispatch or human support.",
        prompt_focus="Stay calm, safety-first, and dispatch-oriented while collecting the exact details needed to move fast.",
        conversion_objective="Capture qualified dispatch requests with location, vehicle, and urgency context.",
        default_goals=["dispatch_qualification", "urgent_triage", "contact_capture", "handoff"],
        default_channels=["website_chat", "ai_telephony", "ai_voice_call"],
        default_lead_capture_fields=["name", "phone", "location", "vehicle", "serviceType"],
        default_enabled_features={
            **DEFAULT_ENABLED_FEATURES,
            "liveTransfer": True,
            "roadsideDispatch": True,
        },
        qualification_notes=[
            "Lead with safety and confirm whether the visitor is in immediate danger.",
            "Collect exact location, vehicle details, and the breakdown type before discussing next steps.",
            "Escalate accidents, injuries, or unsafe roadside conditions immediately.",
        ],
        conversion_stages=["triage", "dispatch_ready", "handoff", "resolved"],
    ),
    "service_business": AgentModeDefinition(
        key="service_business",
        label="Service business booking agent",
        description="Qualifies local-service leads, explains value, and turns web traffic into booked calls, estimates, or appointments.",
        prompt_focus="Operate like a disciplined sales coordinator who educates, qualifies, and books next steps without friction.",
        conversion_objective="Increase quote requests, appointment bookings, and qualified local-service leads.",
        default_goals=["lead_qualification", "appointment_booking", "quote_requests", "follow_up_capture"],
        default_channels=["website_chat", "ai_voice_call", "ai_telephony"],
        default_lead_capture_fields=["name", "email", "phone", "serviceType", "timeline", "location"],
        default_enabled_features={
            **DEFAULT_ENABLED_FEATURES,
            "appointmentBooking": True,
            "smsFollowUp": True,
        },
        qualification_notes=[
            "Clarify service type, urgency, and job location before moving to booking.",
            "Use soft qualification to understand readiness and budget sensitivity.",
            "Offer booking, estimate, or callback based on urgency and intent.",
        ],
        conversion_stages=["awareness", "qualification", "estimate", "booking", "follow_up"],
    ),
    "general_lead_gen": AgentModeDefinition(
        key="general_lead_gen",
        label="General lead generation agent",
        description="Fits B2B and broad marketing sites where the goal is to educate, qualify, and capture high-value leads.",
        prompt_focus="Behave like a revenue development rep who builds interest, surfaces pain, and captures the next best conversion step.",
        conversion_objective="Increase qualified conversations, demo requests, and contact capture for follow-up.",
        default_goals=["lead_qualification", "demo_requests", "contact_capture", "follow_up_capture"],
        default_channels=["website_chat", "ai_voice_call"],
        default_lead_capture_fields=["name", "email", "company", "goal", "timeline", "budget"],
        default_enabled_features={
            **DEFAULT_ENABLED_FEATURES,
            "liveTransfer": True,
        },
        qualification_notes=[
            "Educate before qualifying to avoid sounding like a form.",
            "Capture one data point at a time after giving value.",
            "Move high-intent visitors to demo, call, or direct follow-up.",
        ],
        conversion_stages=["awareness", "interest", "qualification", "intent", "handoff"],
    ),
}

LEGACY_MODE_ALIASES = {
    "lead_qualifier": "general_lead_gen",
    "ecommerce_assistant": "ecommerce",
    "appointment_setter": "service_business",
    "customer_service": "service_business",
    "intake_specialist": "general_lead_gen",
    "general_assistant": "general_lead_gen",
}


def normalize_agent_mode(value: str | None) -> str:
    raw = (value or DEFAULT_AGENT_MODE).strip().lower()
    raw = raw.replace("-", "_").replace(" ", "_")
    raw = LEGACY_MODE_ALIASES.get(raw, raw)
    if raw not in _MODE_REGISTRY:
        return DEFAULT_AGENT_MODE
    return raw


def get_agent_mode_definition(value: str | None) -> AgentModeDefinition:
    return _MODE_REGISTRY[normalize_agent_mode(value)]


def list_agent_modes() -> list[dict[str, Any]]:
    return [
        {
            "key": mode.key,
            "label": mode.label,
            "description": mode.description,
            "promptFocus": mode.prompt_focus,
            "conversionObjective": mode.conversion_objective,
            "defaultGoals": list(mode.default_goals),
            "defaultChannels": list(mode.default_channels),
            "defaultLeadCaptureFields": list(mode.default_lead_capture_fields),
            "defaultEnabledFeatures": dict(mode.default_enabled_features),
            "qualificationNotes": list(mode.qualification_notes),
            "conversionStages": list(mode.conversion_stages),
        }
        for mode in _MODE_REGISTRY.values()
    ]


def normalize_string_list(values: list[str] | None, *, fallback: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        cleaned = str(value).strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized or list(fallback)


def normalize_channels(values: list[str] | None, *, mode: str | None = None) -> list[str]:
    allowed = {item["value"] for item in CHANNEL_OPTIONS}
    fallback = get_agent_mode_definition(mode).default_channels
    return [value for value in normalize_string_list(values, fallback=fallback) if value in allowed] or list(fallback)


def normalize_lead_capture_fields(values: list[str] | None, *, mode: str | None = None) -> list[str]:
    allowed = {item["value"] for item in LEAD_CAPTURE_FIELD_OPTIONS}
    fallback = get_agent_mode_definition(mode).default_lead_capture_fields
    return [value for value in normalize_string_list(values, fallback=fallback) if value in allowed] or list(fallback)


def normalize_enabled_features(values: dict[str, Any] | None, *, mode: str | None = None) -> dict[str, bool]:
    defaults = dict(get_agent_mode_definition(mode).default_enabled_features)
    if not isinstance(values, dict):
        return defaults
    for key in list(defaults.keys()):
        if key in values:
            defaults[key] = bool(values[key])
    return defaults


def normalize_qualification_rules(values: dict[str, Any] | None, *, lead_capture_fields: list[str] | None = None) -> dict[str, Any]:
    required_fields = normalize_string_list(
        list((values or {}).get("requiredFields") or []),
        fallback=[field for field in (lead_capture_fields or DEFAULT_LEAD_CAPTURE_FIELDS) if field in {"name", "email", "phone"}],
    )
    return {
        "requiredFields": required_fields,
        "handoffTriggers": normalize_string_list(list((values or {}).get("handoffTriggers") or []), fallback=[]),
        "disqualifiers": normalize_string_list(list((values or {}).get("disqualifiers") or []), fallback=[]),
        "conversionSignals": normalize_string_list(list((values or {}).get("conversionSignals") or []), fallback=DEFAULT_QUALIFICATION_RULES["conversionSignals"]),
    }

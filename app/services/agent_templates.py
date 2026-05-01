from __future__ import annotations

from typing import Any

from app.services.agent_modes import get_agent_mode_definition

_BUILT_IN_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "ecommerce-sales-closer",
        "name": "Ecommerce sales closer",
        "description": "Optimized for product discovery, objections, upsells, and conversion-focused shopping support.",
        "agentMode": "ecommerce",
        "industry": "ecommerce",
        "config": {
            "goals": ["product_recommendations", "cart_recovery", "upsell_cross_sell", "order_support"],
            "enabledChannels": ["website_chat", "shopify_storefront"],
            "leadCaptureFields": ["name", "email", "phone", "productInterest", "timeline"],
            "enabledFeatures": {
                "knowledgeBase": True,
                "leadCapture": True,
                "qualification": True,
                "appointmentBooking": False,
                "liveTransfer": False,
                "smsFollowUp": True,
                "analytics": True,
                "productRecommendations": True,
                "roadsideDispatch": False,
            },
            "customInstructions": "Guide shoppers toward the best-fit product, reduce hesitation, and recommend useful add-ons only when they improve fit or value.",
        },
    },
    {
        "id": "roadside-dispatch-pro",
        "name": "Roadside dispatch pro",
        "description": "Built for towing, roadside assistance, lockouts, jump starts, and urgent dispatch handoff.",
        "agentMode": "roadside",
        "industry": "automotive",
        "config": {
            "goals": ["dispatch_qualification", "urgent_triage", "contact_capture", "handoff"],
            "enabledChannels": ["website_chat", "ai_voice_call", "ai_telephony"],
            "leadCaptureFields": ["name", "phone", "location", "vehicle", "serviceType"],
            "enabledFeatures": {
                "knowledgeBase": True,
                "leadCapture": True,
                "qualification": True,
                "appointmentBooking": False,
                "liveTransfer": True,
                "smsFollowUp": False,
                "analytics": True,
                "productRecommendations": False,
                "roadsideDispatch": True,
            },
            "customInstructions": "Move fast, stay calm, and prioritize exact location, vehicle details, safety context, and dispatch readiness.",
        },
    },
    {
        "id": "service-booking-accelerator",
        "name": "Service booking accelerator",
        "description": "For home services, local businesses, agencies, and appointment-driven companies.",
        "agentMode": "service_business",
        "industry": "home_services",
        "config": {
            "goals": ["lead_qualification", "appointment_booking", "quote_requests", "follow_up_capture"],
            "enabledChannels": ["website_chat", "ai_voice_call", "ai_telephony"],
            "leadCaptureFields": ["name", "email", "phone", "serviceType", "timeline", "location"],
            "enabledFeatures": {
                "knowledgeBase": True,
                "leadCapture": True,
                "qualification": True,
                "appointmentBooking": True,
                "liveTransfer": False,
                "smsFollowUp": True,
                "analytics": True,
                "productRecommendations": False,
                "roadsideDispatch": False,
            },
            "customInstructions": "Clarify the service needed, urgency, and location, then move the visitor toward booking or a quote request with minimal friction.",
        },
    },
    {
        "id": "b2b-lead-qualifier",
        "name": "B2B lead qualifier",
        "description": "For SaaS, agencies, consultants, and general lead generation sites that want stronger qualification and handoff.",
        "agentMode": "general_lead_gen",
        "industry": "general",
        "config": {
            "goals": ["lead_qualification", "demo_requests", "contact_capture", "follow_up_capture"],
            "enabledChannels": ["website_chat", "ai_voice_call"],
            "leadCaptureFields": ["name", "email", "company", "goal", "timeline", "budget"],
            "enabledFeatures": {
                "knowledgeBase": True,
                "leadCapture": True,
                "qualification": True,
                "appointmentBooking": False,
                "liveTransfer": True,
                "smsFollowUp": False,
                "analytics": True,
                "productRecommendations": False,
                "roadsideDispatch": False,
            },
            "customInstructions": "Educate first, qualify naturally, and move high-intent visitors toward a demo, strategy call, or rapid follow-up.",
        },
    },
]


def list_agent_templates(agent_mode: str | None = None) -> list[dict[str, Any]]:
    if not agent_mode:
        return [dict(template) for template in _BUILT_IN_TEMPLATES]
    normalized_mode = get_agent_mode_definition(agent_mode).key
    return [dict(template) for template in _BUILT_IN_TEMPLATES if template["agentMode"] == normalized_mode]


def get_agent_template(template_id: str) -> dict[str, Any] | None:
    for template in _BUILT_IN_TEMPLATES:
        if template["id"] == template_id:
            return dict(template)
    return None

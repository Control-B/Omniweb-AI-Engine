from __future__ import annotations

from typing import Any

from app.services.agent_modes import get_agent_mode_definition

VOICE_CHANNELS = {"ai_voice_call", "ai_telephony"}
TEXT_CHANNELS = {"website_chat", "shopify_storefront"}

CHANNEL_BEHAVIOR_PROFILES = {
    "text_chat": {
        "key": "text_chat",
        "label": "Text chat widget",
        "channels": ["website_chat", "shopify_storefront"],
        "description": "Use the same Omniweb agent brain, but allow richer written guidance, links, summaries, and structured recommendations.",
        "behavior_rules": [
            "You may be more detailed than voice as long as the response remains useful and conversion-focused.",
            "You may share links, concise summaries, structured guidance, and product or service recommendations.",
            "Use formatting-friendly language that is easy to scan in a widget conversation.",
            "When helpful, summarize options and recommend the best next step clearly.",
        ],
    },
    "voice_realtime": {
        "key": "voice_realtime",
        "label": "Voice widget + AI telephony",
        "channels": ["ai_voice_call", "ai_telephony"],
        "description": "Website voice and phone telephony use the same voice-optimized Omniweb brain profile.",
        "behavior_rules": [
            "Keep responses short, natural, and easy to say out loud.",
            "Ask one question at a time and wait for the answer before continuing.",
            "Confirm important details like names, phone numbers, addresses, dispatch info, booking times, and order-critical data.",
            "Stay interruption-friendly and recover quickly if the caller cuts in or changes direction.",
            "Move efficiently toward booking, dispatch, checkout guidance, or lead capture without sounding rushed.",
        ],
    },
}

UNIVERSAL_RULES = [
    "Never invent policies, pricing, or availability that are not provided.",
    "Ask one question at a time and always lead with value before asking for information.",
    "Capture only the contact and qualification data needed for the next best action.",
    "Escalate to a human whenever the visitor asks for something outside policy, sensitive, or unsafe.",
    "Do not process payments, handle protected financial data, or make legally binding commitments.",
]


def _format_list(title: str, items: list[str]) -> str:
    if not items:
        return ""
    return title + "\n" + "\n".join(f"- {item}" for item in items)


def get_channel_behavior_profiles() -> list[dict[str, Any]]:
    return [
        {
            "key": profile["key"],
            "label": profile["label"],
            "channels": list(profile["channels"]),
            "description": profile["description"],
            "behaviorRules": list(profile["behavior_rules"]),
        }
        for profile in CHANNEL_BEHAVIOR_PROFILES.values()
    ]


def get_effective_channel_profile(channel: str | None) -> dict[str, Any]:
    normalized = (channel or "website_chat").strip()
    if normalized in VOICE_CHANNELS:
        profile = CHANNEL_BEHAVIOR_PROFILES["voice_realtime"]
    else:
        profile = CHANNEL_BEHAVIOR_PROFILES["text_chat"]
    return {
        "key": profile["key"],
        "label": profile["label"],
        "channels": list(profile["channels"]),
        "description": profile["description"],
        "behaviorRules": list(profile["behavior_rules"]),
    }


def build_prompt_preview(config: dict[str, Any]) -> str:
    mode = get_agent_mode_definition(config.get("agentMode"))
    business_name = config.get("businessName") or "this business"
    business_type = config.get("businessType") or config.get("industry") or "general business"
    agent_name = config.get("agentName") or "Omniweb AI"
    website_domain = config.get("websiteDomain") or ""
    goals = list(config.get("goals") or mode.default_goals)
    lead_capture_fields = list(config.get("leadCaptureFields") or mode.default_lead_capture_fields)
    enabled_channels = list(config.get("enabledChannels") or mode.default_channels)
    enabled_features = dict(config.get("enabledFeatures") or mode.default_enabled_features)
    qualification_rules = dict(config.get("qualificationRules") or {})
    required_fields = list(qualification_rules.get("requiredFields") or [])
    handoff_triggers = list(qualification_rules.get("handoffTriggers") or [])
    conversion_signals = list(qualification_rules.get("conversionSignals") or [])
    custom_instructions = (config.get("customInstructions") or "").strip()
    welcome_message = (config.get("welcomeMessage") or "").strip()
    channel_profiles = get_channel_behavior_profiles()
    effective_channel = config.get("channel") or "website_chat"
    effective_profile = get_effective_channel_profile(effective_channel)

    sections = [
        "# Universal Omniweb Revenue Agent",
        f"You are {agent_name}, the conversion-focused AI agent for {business_name}.",
        f"Mode: {mode.label}",
        f"Business type: {business_type}",
        f"Website: {website_domain or 'not provided'}",
        "",
        "## Core Mission",
        mode.prompt_focus,
        f"Primary conversion objective: {mode.conversion_objective}",
        "",
        _format_list("## Active goals", goals),
        _format_list("## Enabled channels", enabled_channels),
        _format_list("## Lead capture fields", lead_capture_fields),
        _format_list("## Qualification guidance", mode.qualification_notes),
        _format_list("## Required fields", required_fields),
        _format_list("## Conversion signals", conversion_signals),
        _format_list("## Human handoff triggers", handoff_triggers),
        "## Universal channel architecture",
        "There is one Omniweb agent brain across text chat, website voice, and AI telephony. Channel behavior changes delivery style, not business logic or conversion intent.",
        f"Current delivery channel: {effective_channel}",
        f"Active behavior profile: {effective_profile['label']}",
    ]

    for profile in channel_profiles:
        sections.extend([
            "",
            f"## Channel behavior profile — {profile['label']}",
            profile["description"],
            *[f"- {rule}" for rule in profile["behaviorRules"]],
        ])

    feature_lines = [f"- {name}: {'enabled' if value else 'disabled'}" for name, value in enabled_features.items()]
    sections.extend([
        "## Feature toggles",
        *feature_lines,
        "",
        "## Conversation rules",
        *[f"- {rule}" for rule in UNIVERSAL_RULES],
    ])

    if welcome_message:
        sections.extend(["", "## Welcome message", welcome_message])

    if custom_instructions:
        sections.extend(["", "## Custom business instructions", custom_instructions])

    return "\n".join(section for section in sections if section is not None)

from __future__ import annotations

from typing import Any

from app.models.models import AgentConfig, Client
from app.services.agent_modes import (
    DEFAULT_AGENT_MODE,
    get_agent_mode_definition,
    list_agent_modes,
    normalize_agent_mode,
    normalize_channels,
    normalize_enabled_features,
    normalize_lead_capture_fields,
    normalize_qualification_rules,
)
from app.services.agent_templates import get_agent_template, list_agent_templates
from app.services.prompt_builder import build_prompt_preview, get_channel_behavior_profiles, get_effective_channel_profile

DEFAULT_AGENT_NAME = "Omniweb AI"
DEFAULT_WELCOME_MESSAGE = (
    "Welcome! I’m here to answer questions, guide visitors toward the best next step, "
    "and help convert interest into action. How can I help today?"
)
DEFAULT_TONE = "professional"
DEFAULT_GOALS = ["lead_qualification", "customer_support", "sales_assistance"]


def _clean_text(value: Any, *, fallback: str = "") -> str:
    if value is None:
        return fallback
    cleaned = str(value).strip()
    return cleaned or fallback


def _clean_goal_list(values: list[str] | None, *, fallback: list[str]) -> list[str]:
    goals: list[str] = []
    for value in values or []:
        cleaned = str(value).strip()
        if cleaned and cleaned not in goals:
            goals.append(cleaned)
    return goals or list(fallback)


def ensure_agent_config_defaults(agent: AgentConfig, tenant: Client | None = None) -> AgentConfig:
    agent.agent_name = _clean_text(getattr(agent, "agent_name", None), fallback=DEFAULT_AGENT_NAME)
    agent.agent_greeting = _clean_text(getattr(agent, "agent_greeting", None), fallback=DEFAULT_WELCOME_MESSAGE)
    agent.tone = _clean_text(getattr(agent, "tone", None), fallback=DEFAULT_TONE)
    if tenant is not None:
        if not getattr(agent, "business_name", None):
            agent.business_name = _clean_text(getattr(tenant, "name", None), fallback="Omniweb Workspace")[:255]
        if not getattr(agent, "business_type", None):
            agent.business_type = _clean_text(getattr(tenant, "industry", None), fallback="general")[:100]
        if not getattr(agent, "industry", None):
            agent.industry = _clean_text(getattr(tenant, "industry", None), fallback="general").lower().replace(" ", "_")[:100]
        if not getattr(agent, "website_domain", None) and getattr(tenant, "website_url", None):
            website = str(tenant.website_url).strip().replace("https://", "").replace("http://", "").rstrip("/")
            agent.website_domain = website[:255]

    mode = normalize_agent_mode(getattr(agent, "agent_mode", None))
    mode_definition = get_agent_mode_definition(mode)
    agent.agent_mode = mode_definition.key
    agent.goals = _clean_goal_list(getattr(agent, "goals", None), fallback=mode_definition.default_goals)
    agent.enabled_channels = normalize_channels(getattr(agent, "enabled_channels", None), mode=mode_definition.key)
    agent.lead_capture_fields = normalize_lead_capture_fields(getattr(agent, "lead_capture_fields", None), mode=mode_definition.key)
    agent.enabled_features = normalize_enabled_features(getattr(agent, "enabled_features", None), mode=mode_definition.key)
    agent.qualification_rules = normalize_qualification_rules(
        getattr(agent, "qualification_rules", None),
        lead_capture_fields=agent.lead_capture_fields,
    )
    if not getattr(agent, "custom_instructions", None):
        agent.custom_instructions = None
    agent.system_prompt = build_prompt_preview(serialize_agent_config(agent, include_prompt=False))
    return agent


def serialize_agent_config(agent: AgentConfig, *, include_prompt: bool = True) -> dict[str, Any]:
    mode_definition = get_agent_mode_definition(getattr(agent, "agent_mode", None))
    payload = {
        "id": str(agent.id),
        "tenantId": str(agent.client_id),
        "agentName": agent.agent_name,
        "welcomeMessage": agent.agent_greeting,
        "tone": getattr(agent, "tone", DEFAULT_TONE) or DEFAULT_TONE,
        "goals": list(getattr(agent, "goals", None) or mode_definition.default_goals),
        "active": bool(getattr(agent, "active", True)),
        "businessName": getattr(agent, "business_name", "") or "",
        "businessType": getattr(agent, "business_type", None),
        "industry": getattr(agent, "industry", None),
        "websiteDomain": getattr(agent, "website_domain", None),
        "bookingUrl": getattr(agent, "booking_url", None),
        "agentMode": mode_definition.key,
        "enabledChannels": list(getattr(agent, "enabled_channels", None) or mode_definition.default_channels),
        "leadCaptureFields": list(getattr(agent, "lead_capture_fields", None) or mode_definition.default_lead_capture_fields),
        "enabledFeatures": dict(getattr(agent, "enabled_features", None) or mode_definition.default_enabled_features),
        "qualificationRules": dict(getattr(agent, "qualification_rules", None) or {}),
        "customInstructions": getattr(agent, "custom_instructions", None),
        "channelBehaviorProfiles": get_channel_behavior_profiles(),
        "createdAt": agent.created_at.isoformat() if getattr(agent, "created_at", None) else None,
        "updatedAt": agent.updated_at.isoformat() if getattr(agent, "updated_at", None) else None,
        "modeDefinition": {
            "key": mode_definition.key,
            "label": mode_definition.label,
            "description": mode_definition.description,
            "conversionObjective": mode_definition.conversion_objective,
            "qualificationNotes": list(mode_definition.qualification_notes),
            "conversionStages": list(mode_definition.conversion_stages),
        },
        "availableModes": list_agent_modes(),
    }
    if include_prompt:
        payload["promptPreview"] = build_prompt_preview(payload)
    return payload


def apply_agent_config_updates(agent: AgentConfig, updates: dict[str, Any]) -> AgentConfig:
    if "agentName" in updates:
        agent.agent_name = _clean_text(updates.get("agentName"), fallback=agent.agent_name or DEFAULT_AGENT_NAME)[:100]
    if "welcomeMessage" in updates:
        agent.agent_greeting = _clean_text(updates.get("welcomeMessage"), fallback=agent.agent_greeting or DEFAULT_WELCOME_MESSAGE)
    if "tone" in updates:
        agent.tone = _clean_text(updates.get("tone"), fallback=DEFAULT_TONE)[:30]
    if "businessName" in updates:
        agent.business_name = _clean_text(updates.get("businessName"), fallback=agent.business_name or "")[:255]
    if "businessType" in updates:
        agent.business_type = _clean_text(updates.get("businessType"), fallback=agent.business_type or "")[:100] or None
    if "industry" in updates:
        normalized_industry = _clean_text(updates.get("industry"), fallback=agent.industry or "general").lower().replace(" ", "_")
        agent.industry = normalized_industry[:100]
    if "websiteDomain" in updates:
        website_domain = _clean_text(updates.get("websiteDomain"), fallback=agent.website_domain or "")
        for prefix in ("https://", "http://", "www."):
            if website_domain.startswith(prefix):
                website_domain = website_domain[len(prefix):]
        agent.website_domain = website_domain.rstrip("/")[:255] or None
    if "bookingUrl" in updates:
        agent.booking_url = _clean_text(updates.get("bookingUrl"), fallback=agent.booking_url or "") or None
    if "active" in updates:
        agent.active = bool(updates.get("active"))

    next_mode = normalize_agent_mode(updates.get("agentMode", getattr(agent, "agent_mode", DEFAULT_AGENT_MODE)))
    mode_definition = get_agent_mode_definition(next_mode)
    agent.agent_mode = next_mode
    agent.goals = _clean_goal_list(updates.get("goals", getattr(agent, "goals", None)), fallback=mode_definition.default_goals)
    agent.enabled_channels = normalize_channels(updates.get("enabledChannels", getattr(agent, "enabled_channels", None)), mode=next_mode)
    agent.lead_capture_fields = normalize_lead_capture_fields(updates.get("leadCaptureFields", getattr(agent, "lead_capture_fields", None)), mode=next_mode)
    agent.enabled_features = normalize_enabled_features(updates.get("enabledFeatures", getattr(agent, "enabled_features", None)), mode=next_mode)
    agent.qualification_rules = normalize_qualification_rules(
        updates.get("qualificationRules", getattr(agent, "qualification_rules", None)),
        lead_capture_fields=agent.lead_capture_fields,
    )
    if "customInstructions" in updates:
        custom_instructions = _clean_text(updates.get("customInstructions"), fallback="")
        agent.custom_instructions = custom_instructions or None

    agent.system_prompt = build_prompt_preview(serialize_agent_config(agent, include_prompt=False))
    return agent


def apply_agent_template(agent: AgentConfig, template_id: str) -> dict[str, Any]:
    template = get_agent_template(template_id)
    if not template:
        raise ValueError("Unknown template")
    apply_agent_config_updates(
        agent,
        {
            "agentMode": template["agentMode"],
            "industry": template.get("industry"),
            **dict(template.get("config") or {}),
        },
    )
    return template


def list_templates_payload(agent_mode: str | None = None) -> list[dict[str, Any]]:
    return list_agent_templates(agent_mode)


def build_prompt_for_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized_mode = normalize_agent_mode(payload.get("agentMode"))
    mode_definition = get_agent_mode_definition(normalized_mode)
    channel = payload.get("channel") or "website_chat"
    preview_payload = {
        "agentName": payload.get("agentName") or DEFAULT_AGENT_NAME,
        "welcomeMessage": payload.get("welcomeMessage") or DEFAULT_WELCOME_MESSAGE,
        "businessName": payload.get("businessName") or "Omniweb Workspace",
        "businessType": payload.get("businessType") or payload.get("industry") or "general",
        "industry": payload.get("industry") or "general",
        "websiteDomain": payload.get("websiteDomain") or "",
        "agentMode": normalized_mode,
        "goals": _clean_goal_list(payload.get("goals"), fallback=mode_definition.default_goals),
        "enabledChannels": normalize_channels(payload.get("enabledChannels"), mode=normalized_mode),
        "leadCaptureFields": normalize_lead_capture_fields(payload.get("leadCaptureFields"), mode=normalized_mode),
        "enabledFeatures": normalize_enabled_features(payload.get("enabledFeatures"), mode=normalized_mode),
        "qualificationRules": normalize_qualification_rules(payload.get("qualificationRules"), lead_capture_fields=payload.get("leadCaptureFields")),
        "customInstructions": _clean_text(payload.get("customInstructions"), fallback="") or None,
        "channel": channel,
    }
    return {
        "agentMode": normalized_mode,
        "channel": channel,
        "channelBehaviorProfiles": get_channel_behavior_profiles(),
        "effectiveChannelProfile": get_effective_channel_profile(channel),
        "modeDefinition": {
            "key": mode_definition.key,
            "label": mode_definition.label,
            "description": mode_definition.description,
            "conversionObjective": mode_definition.conversion_objective,
            "conversionStages": list(mode_definition.conversion_stages),
        },
        "promptPreview": build_prompt_preview(preview_payload),
    }


def infer_conversion_stage(message: str, agent_mode: str) -> str:
    normalized = (message or "").lower()
    mode_definition = get_agent_mode_definition(agent_mode)
    if any(token in normalized for token in ["buy", "checkout", "sign up", "book", "dispatch", "tow now", "call me now"]):
        return mode_definition.conversion_stages[min(3, len(mode_definition.conversion_stages) - 1)]
    if any(token in normalized for token in ["price", "pricing", "quote", "cost", "compare", "availability"]):
        return mode_definition.conversion_stages[min(1, len(mode_definition.conversion_stages) - 1)]
    if any(token in normalized for token in ["help", "issue", "support", "return", "refund"]):
        return mode_definition.conversion_stages[-1]
    return mode_definition.conversion_stages[0]


def run_agent_test(config: dict[str, Any], message: str) -> dict[str, Any]:
    normalized_mode = normalize_agent_mode(config.get("agentMode"))
    mode_definition = get_agent_mode_definition(normalized_mode)
    conversion_stage = infer_conversion_stage(message, normalized_mode)
    channel = str(config.get("channel") or "website_chat")
    effective_profile = get_effective_channel_profile(channel)
    lead_fields = list(config.get("leadCaptureFields") or mode_definition.default_lead_capture_fields)
    next_field = lead_fields[0] if lead_fields else None
    if effective_profile["key"] == "voice_realtime":
        response = (
            f"Got it. I’m handling this as a {mode_definition.label.lower()}. "
            f"I’d keep it short and move this toward {conversion_stage.replace('_', ' ')} quickly."
        )
    else:
        response = (
            f"Thanks — I’m handling this as a {mode_definition.label.lower()}. "
            f"I’d focus on moving this conversation from {conversion_stage.replace('_', ' ')} toward {mode_definition.conversion_objective.lower()}."
        )
    if next_field:
        response += f" Next, I’d naturally work toward capturing {next_field.replace('productInterest', 'product interest').replace('serviceType', 'service type')} if it hasn’t been shared yet."

    return {
        "input": message,
        "response": response,
        "agentMode": normalized_mode,
        "channel": channel,
        "effectiveChannelProfile": effective_profile,
        "conversionStage": conversion_stage,
        "analyticsTags": {
            "agentMode": normalized_mode,
            "channel": channel,
            "conversionStage": conversion_stage,
        },
        "suggestedNextField": next_field,
        "promptPreview": build_prompt_for_payload(config)["promptPreview"],
    }

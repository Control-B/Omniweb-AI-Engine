"""Shared Omniweb AI brain for chat, web voice, and Retell telephony.

Providers own transport. This service owns tenant context, prompt composition,
lead/escalation decisions, and channel-specific response packaging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, TenantEscalationRule
from app.services.prompt_engine import compose_system_prompt

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class BrainRequest:
    tenant_id: UUID
    channel_type: str
    user_message: str | None = None
    transcript_chunk: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainResponse:
    response_text: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    escalation: dict[str, Any] = field(default_factory=dict)
    lead_fields: dict[str, Any] = field(default_factory=dict)


def _coerce_str_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, dict):
        return [str(value).strip() for value in raw.values() if str(value).strip()]
    return []


def _coerce_services(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, dict):
        return [str(key).strip() for key in raw if str(key).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _extract_lead_fields(message: str, metadata: dict[str, Any]) -> dict[str, Any]:
    lead: dict[str, Any] = {}
    caller_phone = metadata.get("caller_phone") or metadata.get("from_number")
    if caller_phone:
        lead["phone"] = str(caller_phone)
    if "@" in message:
        for token in message.replace(",", " ").split():
            if "@" in token and "." in token:
                lead["email"] = token.strip(".,;:()[]")
                break
    return lead


class OmniwebBrainService:
    """One shared tenant-aware brain used across provider channels."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_agent_config(self, tenant_id: UUID) -> AgentConfig:
        result = await self.db.execute(select(AgentConfig).where(AgentConfig.client_id == tenant_id))
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError("No agent configuration for tenant")
        return config

    async def get_escalation_rule(self, tenant_id: UUID, channel_type: str) -> TenantEscalationRule | None:
        result = await self.db.execute(
            select(TenantEscalationRule).where(
                TenantEscalationRule.tenant_id == tenant_id,
                TenantEscalationRule.channel_type == channel_type,
            )
        )
        return result.scalar_one_or_none()

    def compose_prompt(self, config: AgentConfig, channel_type: str) -> str:
        return compose_channel_prompt(config, channel_type)

    async def run(self, request: BrainRequest) -> BrainResponse:
        config = await self.get_agent_config(request.tenant_id)
        rule = await self.get_escalation_rule(request.tenant_id, request.channel_type)
        message = (request.user_message or request.transcript_chunk or "").strip()
        escalation = self._decide_escalation(config, rule, message)
        lead_fields = _extract_lead_fields(message, request.metadata)

        if not message:
            return BrainResponse(
                response_text=config.agent_greeting or "Thanks for calling. How can I help today?",
                escalation=escalation,
                lead_fields=lead_fields,
            )

        response_text = await self._generate_response(config, request.channel_type, message, request.metadata)
        actions: list[dict[str, Any]] = []
        if escalation.get("triggered"):
            actions.append({"type": "escalate", "payload": escalation})

        return BrainResponse(
            response_text=response_text,
            actions=actions,
            escalation=escalation,
            lead_fields=lead_fields,
        )

    def _decide_escalation(
        self,
        config: AgentConfig,
        rule: TenantEscalationRule | None,
        message: str,
    ) -> dict[str, Any]:
        keywords = [
            "human",
            "representative",
            "manager",
            "angry",
            "lawsuit",
            "legal",
            "refund",
            "cancel",
        ]
        keywords.extend(_coerce_str_list(config.custom_escalation_triggers))
        if rule and rule.enabled:
            keywords.extend(_coerce_str_list(rule.trigger_keywords))

        normalized = message.lower()
        matched = [keyword for keyword in keywords if keyword and keyword.lower() in normalized]
        phone = (rule.human_escalation_phone if rule else None) or config.handoff_phone
        email = (rule.fallback_email if rule else None) or config.handoff_email
        return {
            "triggered": bool(matched),
            "reason": matched[0] if matched else None,
            "human_escalation_phone": phone,
            "fallback_email": email,
            "message": config.handoff_message,
        }

    async def _generate_response(
        self,
        config: AgentConfig,
        channel_type: str,
        message: str,
        metadata: dict[str, Any],
    ) -> str:
        if not settings.openai_configured:
            return self._fallback_response(config, message)

        try:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            completion = await client.chat.completions.create(
                model=(config.llm_model or "").strip() or settings.OPENAI_MODEL or "gpt-4o",
                messages=[
                    {"role": "system", "content": self.compose_prompt(config, channel_type)},
                    {"role": "user", "content": message},
                ],
                temperature=min(max(config.temperature or 0.4, 0), 1),
                max_tokens=240,
                metadata={
                    "tenant_id": str(config.client_id),
                    "channel_type": channel_type,
                    "provider": str(metadata.get("provider") or "omniweb"),
                },
            )
            text = completion.choices[0].message.content if completion.choices else None
            return (text or "").strip() or self._fallback_response(config, message)
        except Exception as exc:
            logger.error("Omniweb brain OpenAI response failed", tenant_id=str(config.client_id), error=str(exc))
            return self._fallback_response(config, message)

    def _fallback_response(self, config: AgentConfig, message: str) -> str:
        business = config.business_name or "the team"
        return (
            f"Got it. I can help with that for {business}. "
            "Tell me one quick detail about what you need, and I’ll guide you to the best next step."
        )


def compose_channel_prompt(config: AgentConfig, channel_type: str) -> str:
    """Compose the shared tenant brain prompt with channel-specific behavior."""
    owner_instructions = config.custom_instructions or config.system_prompt
    custom_context = config.custom_context
    if custom_context and owner_instructions and custom_context.strip() == owner_instructions.strip():
        custom_context = None
    base_prompt = compose_system_prompt(
        agent_name=config.agent_name or "Omniweb AI",
        business_name=config.business_name or "this business",
        industry_slug=config.industry or "general",
        agent_mode=config.agent_mode,
        business_type=config.business_type,
        services=_coerce_services(config.services),
        business_hours=config.business_hours if isinstance(config.business_hours, dict) else {},
        timezone=config.timezone or "America/New_York",
        booking_url=config.booking_url,
        after_hours_message=config.after_hours_message or "",
        custom_prompt=owner_instructions,
        custom_guardrails=_coerce_str_list(config.custom_guardrails),
        custom_escalation_triggers=_coerce_str_list(config.custom_escalation_triggers),
        custom_context=custom_context,
    )
    channel_block = {
        "chat": "Channel: website chat. Keep replies concise, helpful, and action-oriented.",
        "web_voice": (
            "Channel: web voice. Speak naturally, one idea at a time, and allow interruptions. "
            "Use short, conversational replies that sound spoken rather than written. "
            "Do not answer random noises, music, TV, side conversations, or unclear fragments. "
            "Only respond when the visitor clearly addresses you; if the audio is garbled or not directed at you, stay quiet."
        ),
        "ai_telephony": (
            "Channel: AI telephony over a phone call. This is the same Omniweb agent brain, "
            "but the caller hears spoken responses. Be warm, concise, collect lead details naturally, "
            "and escalate when the caller asks for a human or the issue is outside safe handling."
        ),
    }.get(channel_type, f"Channel: {channel_type}.")
    return f"{base_prompt}\n\n## Channel Context\n{channel_block}"

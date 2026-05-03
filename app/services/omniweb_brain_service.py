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

    def compose_prompt(
        self,
        config: AgentConfig,
        channel_type: str,
        *,
        language: str | None = None,
    ) -> str:
        return compose_channel_prompt(config, channel_type, language=language)

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
        language = (
            metadata.get("detected_language")
            or metadata.get("language")
            or metadata.get("detectedLanguage")
            or None
        )
        if not settings.openai_configured:
            logger.warning("Omniweb brain falling back: OpenAI not configured", tenant_id=str(config.client_id))
            return self._fallback_response(config, message, language=language)

        try:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            completion = await client.chat.completions.create(
                model=(config.llm_model or "").strip() or settings.OPENAI_MODEL or "gpt-4o",
                messages=[
                    {"role": "system", "content": self.compose_prompt(config, channel_type, language=language)},
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
            cleaned = (text or "").strip()
            if cleaned:
                return cleaned
            logger.warning(
                "Omniweb brain returned empty completion",
                tenant_id=str(config.client_id),
                channel_type=channel_type,
            )
            return self._fallback_response(config, message, language=language)
        except Exception as exc:
            logger.error(
                "Omniweb brain OpenAI response failed",
                tenant_id=str(config.client_id),
                channel_type=channel_type,
                error=str(exc),
            )
            return self._fallback_response(config, message, language=language)

    def _fallback_response(
        self,
        config: AgentConfig,
        message: str,
        *,
        language: str | None = None,
    ) -> str:
        business = config.business_name or "our team"
        contact = config.handoff_email
        normalized = (language or "en").strip().lower().split("-")[0]
        templates = {
            "en": (
                "Sorry — I'm having trouble responding right now. Please try again in a moment, "
                f"or share an email and {business} will follow up directly{f' at {contact}' if contact else ''}."
            ),
            "es": (
                "Lo siento — estoy teniendo problemas para responder ahora mismo. Inténtalo de nuevo en un momento "
                f"o déjame un correo y {business} te responderá directamente{f' a {contact}' if contact else ''}."
            ),
            "fr": (
                "Désolé — j'ai du mal à répondre pour le moment. Réessayez dans un instant, "
                f"ou laissez-moi un e-mail et {business} vous recontactera directement{f' à {contact}' if contact else ''}."
            ),
            "de": (
                "Entschuldigung — ich habe gerade Probleme zu antworten. Bitte versuchen Sie es gleich erneut, "
                f"oder hinterlassen Sie eine E-Mail und {business} meldet sich direkt zurück{f' unter {contact}' if contact else ''}."
            ),
            "pt": (
                "Desculpe — estou com dificuldade para responder agora. Tente novamente em instantes "
                f"ou deixe um e-mail e a {business} retornará diretamente{f' em {contact}' if contact else ''}."
            ),
            "it": (
                "Mi dispiace — sto avendo problemi a rispondere in questo momento. Riprova tra poco, "
                f"oppure lasciami un'email e {business} ti risponderà direttamente{f' a {contact}' if contact else ''}."
            ),
        }
        return templates.get(normalized, templates["en"])


def compose_channel_prompt(
    config: AgentConfig,
    channel_type: str,
    *,
    language: str | None = None,
) -> str:
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

    chat_pattern = (
        "Reply pattern (use every turn):\n"
        "1. Directly answer the visitor's question with one concrete, useful detail or recommendation grounded in the business context above. "
        "Never reply with vague filler like 'Tell me one quick detail about what you need' or 'How can I help you'.\n"
        "2. Recommend the most relevant service, product, or next step for this business when it fits.\n"
        "3. Ask ONE specific qualifying question only when you genuinely need more information to help.\n"
        "Keep replies under 3 sentences, conversational, and conversion-focused. Match the visitor's language."
    )

    voice_pattern = (
        "The opening greeting has ALREADY been delivered automatically by the channel before you were invoked. "
        "DO NOT greet, introduce yourself, or repeat the welcome — the user has already heard it. "
        "Start by listening for their first request.\n\n"
        "When the user speaks, follow this pattern every turn:\n"
        "1. Directly answer their question with one concrete useful detail or recommendation grounded in the business context above. "
        "Never reply with vague filler like 'Tell me one quick detail' or 'How can I help you'.\n"
        "2. Recommend the most relevant service, product, or next step for this business when it fits.\n"
        "3. Ask ONE specific qualifying question only when you genuinely need more info to help.\n"
        "Keep replies short, spoken, and natural. Allow interruptions. "
        "Only respond when clearly addressed; if audio is garbled or not directed at you, stay quiet."
    )

    channel_block = {
        "chat": f"Channel: website chat. {chat_pattern}",
        "web_voice": f"Channel: web voice (real-time speech). {voice_pattern}",
        "ai_telephony": (
            "Channel: AI telephony over a phone call. The opening greeting has already been delivered by the channel — "
            "do not greet again. Be warm, concise, follow the answer→recommend→qualify pattern, collect lead details "
            "naturally, and escalate when the caller asks for a human or the issue is outside safe handling."
        ),
    }.get(channel_type, f"Channel: {channel_type}.")

    sections = [base_prompt, "## Channel Context", channel_block]

    normalized_language = (language or "").strip().lower()
    if normalized_language and normalized_language not in {"auto", "multi", ""}:
        language_name = _LANGUAGE_DISPLAY_NAMES.get(normalized_language, normalized_language)
        sections.append("## Language")
        sections.append(
            f"Respond in {language_name}. If the user writes or speaks in a different language, "
            "respond in the user's language unless the business settings explicitly require otherwise."
        )
    elif normalized_language in {"auto", "multi"}:
        sections.append("## Language")
        sections.append(
            "Respond in the visitor's own language. Detect their language from what they write or speak "
            "and reply in that same language. Fall back to English only when their language cannot be determined."
        )

    return "\n\n".join(sections)


_LANGUAGE_DISPLAY_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "sv": "Swedish",
    "ro": "Romanian",
    "ru": "Russian",
    "uk": "Ukrainian",
    "pl": "Polish",
    "ar": "Arabic",
    "tr": "Turkish",
    "hi": "Hindi",
    "bn": "Bengali",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "tl": "Filipino",
    "sw": "Swahili",
    "kri": "Krio",
    "su": "Sundanese",
}

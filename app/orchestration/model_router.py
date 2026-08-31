"""Model Router & Intelligence Abstraction for Omniweb Contact Center.

Provides dynamic routing across model tiers:
- FAST_INTENT: Ultra-low latency classification (< 200ms)
- PRIMARY_CONVERSATION: Balanced conversational intelligence for specialist agents
- HIGH_REASONING: Deep cognitive reasoning for DeepAgents delegation
- MULTIMODAL_SPEECH: Real-time direct speech models
- EMBEDDINGS: Semantic search vectors for tenant RAG
"""
from __future__ import annotations

import json
import time
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, Field


try:
    from app.core.config import get_settings
    from app.core.logging import get_logger
    from app.core.telemetry import MetricTracker, get_current_correlation
except ImportError:
    from backend.app.core.config import get_settings  # type: ignore[no-redef]
    from backend.app.core.logging import get_logger  # type: ignore[no-redef]
    from backend.app.core.telemetry import MetricTracker, get_current_correlation  # type: ignore[no-redef]

logger = get_logger(__name__)
settings = get_settings()


T = TypeVar("T", bound=BaseModel)


class ModelTier(str, Enum):
    FAST_INTENT = "fast_intent"
    PRIMARY_CONVERSATION = "primary_conversation"
    HIGH_REASONING = "high_reasoning"
    MULTIMODAL_SPEECH = "multimodal_speech"
    EMBEDDING = "embedding"


class ModelResponse(BaseModel):
    """Pydantic model representing a normalized model generation response."""
    content: str
    model_name: str
    tier: ModelTier
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    structured_data: Any | None = None
    finish_reason: str = "stop"
    raw_response: dict[str, Any] = Field(default_factory=dict)



class ModelRouter:
    """Intelligent provider-agnostic router with fallback and observability."""

    def __init__(self):
        self._openai_client = None
        self._gemini_client = None

    def resolve_model_name(self, tier: ModelTier) -> str:
        """Resolve model name for a given tier based on configuration."""
        if tier == ModelTier.FAST_INTENT:
            return settings.DEFAULT_INTENT_MODEL or "gemini-2.0-flash-lite"
        elif tier == ModelTier.PRIMARY_CONVERSATION:
            return settings.DEFAULT_CONVERSATION_MODEL or "gemini-2.0-flash"
        elif tier == ModelTier.HIGH_REASONING:
            return settings.DEFAULT_REASONING_MODEL or "gemini-2.0-pro"
        elif tier == ModelTier.MULTIMODAL_SPEECH:
            return settings.GEMINI_LIVE_SPEECH_MODEL or "gemini-2.0-flash-exp"
        elif tier == ModelTier.EMBEDDING:
            return settings.DEFAULT_EMBEDDING_MODEL or "text-embedding-004"
        return "gemini-2.0-flash"

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        tier: ModelTier = ModelTier.PRIMARY_CONVERSATION,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> ModelResponse:
        """Execute text generation against the resolved model profile."""
        start_time = time.perf_counter()
        model_name = self.resolve_model_name(tier)
        corr = get_current_correlation()

        logger.info(
            f"Generating response using [{tier.value}]: {model_name} (corr={corr.correlation_id})"
        )

        # 1. Try Gemini if configured
        if settings.gemini_configured:
            try:
                res = await self._generate_gemini(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
                duration_ms = (time.perf_counter() - start_time) * 1000
                res.duration_ms = duration_ms
                res.tier = tier
                MetricTracker.record_turn_latency(stage=f"llm_{tier.value}", duration_ms=duration_ms)
                return res
            except Exception as exc:
                logger.warning(f"Gemini generation failed, trying OpenAI fallback: {exc}")

        # 2. Try OpenAI fallback
        if settings.openai_configured:
            try:
                res = await self._generate_openai(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model_name=settings.OPENAI_MODEL if tier != ModelTier.FAST_INTENT else "gpt-4o-mini",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
                duration_ms = (time.perf_counter() - start_time) * 1000
                res.duration_ms = duration_ms
                res.tier = tier
                MetricTracker.record_turn_latency(stage=f"llm_{tier.value}", duration_ms=duration_ms)
                return res
            except Exception as exc:
                logger.warning(f"OpenAI generation failed: {exc}")

        # 3. Deterministic fallback for dev/test environments without active API keys
        duration_ms = (time.perf_counter() - start_time) * 1000
        fallback_text = self._mock_generation(prompt, system_instruction, json_mode)
        return ModelResponse(
            content=fallback_text,
            model_name=f"{model_name}-fallback",
            tier=tier,
            input_tokens=len(prompt) // 4,
            output_tokens=len(fallback_text) // 4,
            duration_ms=duration_ms,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system_instruction: str | None = None,
        tier: ModelTier = ModelTier.FAST_INTENT,
        temperature: float = 0.2,
    ) -> T:
        """Generate structured Pydantic data."""
        augmented_system = (
            f"{system_instruction or ''}\n"
            f"You MUST respond ONLY with valid JSON conforming to this schema:\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}"
        )

        resp = await self.generate_text(
            prompt=prompt,
            system_instruction=augmented_system,
            tier=tier,
            temperature=temperature,
            json_mode=True,
        )

        try:
            # Strip markdown fence if present
            cleaned = resp.content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            return schema.model_validate(data)
        except Exception as exc:
            logger.error(f"Failed to parse structured model output into {schema.__name__}: {exc}")
            # Return a default instance if parsing fails
            return schema.model_construct()

    async def _generate_gemini(
        self,
        prompt: str,
        system_instruction: str | None,
        model_name: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelResponse:
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates returned from Gemini")
        
        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        usage = data.get("usageMetadata", {})
        
        return ModelResponse(
            content=content,
            model_name=model_name,
            tier=ModelTier.PRIMARY_CONVERSATION,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            raw_response=data,
        )

    async def _generate_openai(
        self,
        prompt: str,
        system_instruction: str | None,
        model_name: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelResponse:
        from openai import AsyncOpenAI

        if not self._openai_client:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._openai_client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage

        return ModelResponse(
            content=content,
            model_name=model_name,
            tier=ModelTier.PRIMARY_CONVERSATION,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            raw_response={"id": response.id, "finish_reason": choice.finish_reason},
        )

    def _mock_generation(self, prompt: str, system_instruction: str | None, json_mode: bool) -> str:
        """Deterministic mock response for offline development and testing."""
        prompt_lower = prompt.lower()
        if json_mode:
            # Extract customer message if formatted in prompt
            target_text = prompt_lower
            if 'customer message: "' in prompt_lower:
                try:
                    target_text = prompt_lower.split('customer message: "')[1].split('"')[0]
                except Exception:
                    target_text = prompt_lower

            intent = "general_inquiry"
            sentiment = "positive"
            urgency = "medium"

            if any(k in target_text for k in ["human", "manager", "unacceptable", "representative", "escalat"]):
                intent = "human_escalation"
                sentiment = "angry"
                urgency = "critical"
            elif any(k in target_text for k in ["bill", "invoice", "refund", "charge", "balance", "$"]):
                intent = "billing_inquiry"
            elif any(k in target_text for k in ["book", "appointment", "schedule", "tomorrow", "calendar"]):
                intent = "appointment_booking"
            elif any(k in target_text for k in ["pricing", "cost", "reps", "switch", "sales", "buy", "package"]):
                intent = "sales_inquiry"
            elif any(k in target_text for k in ["error", "diagnostic", "troubleshoot", "down", "outage", "broken"]):
                intent = "technical_issue"
            elif any(k in target_text for k in ["cancel", "terminate", "retention"]):
                intent = "cancel_subscription"
                urgency = "high"

            return json.dumps({
                "intent": intent,
                "secondary_intents": [],
                "language": "en",
                "sentiment": sentiment,
                "urgency": urgency,
                "extracted_entities": {},
                "summary": f"Inquiry classified as {intent}",
            })
        return "Thank you for reaching Omniweb Contact Center. I can assist you with your inquiry right away."




_model_router = ModelRouter()


def get_model_router() -> ModelRouter:
    """Singleton getter for the model router."""
    return _model_router

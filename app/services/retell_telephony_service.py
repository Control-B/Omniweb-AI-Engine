"""Retell telephony orchestration for Omniweb's shared AI brain."""

from __future__ import annotations

import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import (
    AgentConfig,
    Client,
    TenantCallLog,
    TenantChannel,
    TenantEscalationRule,
    TenantRetellAgent,
    TenantUsageMetering,
)
from app.services import retell_service
from app.services.omniweb_brain_service import BrainRequest, OmniwebBrainService, compose_channel_prompt

logger = get_logger(__name__)
settings = get_settings()

CHANNEL_TYPE = "ai_telephony"
PROVIDER = "retell"
RETELL_PROVIDER_COST_PER_MINUTE = 0.07
SUBSCRIBER_BILLED_PER_MINUTE = 0.12
PLAN_LIMITS = {
    "starter": 120,
    "growth": 600,
    "pro": 1200,
    "agency": 3000,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or utcnow()
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def clean_phone(value: str | None) -> str:
    return (value or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


def transcript_to_text(transcript: Any) -> str:
    if isinstance(transcript, str):
        return transcript
    if isinstance(transcript, list):
        lines: list[str] = []
        for item in transcript:
            if isinstance(item, dict):
                speaker = item.get("role") or item.get("speaker") or "caller"
                text = item.get("content") or item.get("text") or ""
                if text:
                    lines.append(f"{speaker}: {text}")
        return "\n".join(lines)
    return ""


class RetellTelephonyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_channel(self, tenant_id: UUID) -> TenantChannel:
        result = await self.db.execute(
            select(TenantChannel).where(
                TenantChannel.tenant_id == tenant_id,
                TenantChannel.channel_type == CHANNEL_TYPE,
            )
        )
        channel = result.scalar_one_or_none()
        if channel:
            return channel
        channel = TenantChannel(
            tenant_id=tenant_id,
            channel_type=CHANNEL_TYPE,
            provider=PROVIDER,
            status="disabled",
            config_json={},
        )
        self.db.add(channel)
        return channel

    async def get_or_create_retell_agent(self, tenant_id: UUID) -> TenantRetellAgent:
        result = await self.db.execute(select(TenantRetellAgent).where(TenantRetellAgent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if agent:
            return agent
        agent = TenantRetellAgent(
            tenant_id=tenant_id,
            status="provisioning",
            webhook_url=f"{settings.ENGINE_BASE_URL.rstrip('/')}/api/retell/webhook",
        )
        self.db.add(agent)
        return agent

    async def get_or_create_escalation_rule(self, tenant_id: UUID) -> TenantEscalationRule:
        result = await self.db.execute(
            select(TenantEscalationRule).where(
                TenantEscalationRule.tenant_id == tenant_id,
                TenantEscalationRule.channel_type == CHANNEL_TYPE,
            )
        )
        rule = result.scalar_one_or_none()
        if rule:
            return rule
        rule = TenantEscalationRule(
            tenant_id=tenant_id,
            channel_type=CHANNEL_TYPE,
            trigger_keywords=["human", "representative", "manager", "urgent", "legal", "refund"],
            enabled=True,
        )
        self.db.add(rule)
        return rule

    async def provision(self, tenant_id: UUID, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
        channel = await self.get_or_create_channel(tenant_id)
        tenant_agent = await self.get_or_create_retell_agent(tenant_id)
        escalation = await self.get_or_create_escalation_rule(tenant_id)
        agent_config = await self._get_agent_config(tenant_id)

        merged = dict(channel.config_json or {})
        merged.update(config or {})
        channel.status = "provisioning"
        channel.config_json = merged

        if config:
            tenant_agent.human_escalation_phone = clean_phone(config.get("human_escalation_phone")) or tenant_agent.human_escalation_phone
            tenant_agent.fallback_email = (config.get("fallback_email") or tenant_agent.fallback_email or "").strip() or None
            escalation.human_escalation_phone = tenant_agent.human_escalation_phone
            escalation.fallback_email = tenant_agent.fallback_email
            if isinstance(config.get("business_hours"), dict):
                escalation.business_hours = config["business_hours"]

        try:
            if not tenant_agent.retell_phone_number:
                tenant_agent.retell_phone_number = await self._first_retell_phone_number()

            if not tenant_agent.retell_agent_id:
                tenant_agent.retell_agent_id = await self._create_or_prepare_retell_agent(agent_config, tenant_agent)
            else:
                await self._sync_retell_agent(agent_config, tenant_agent)

            agent_config.retell_agent_id = tenant_agent.retell_agent_id
            channel.status = "active" if tenant_agent.retell_agent_id else "error"
            tenant_agent.status = channel.status
            tenant_agent.last_synced_at = utcnow()
            if channel.status == "active":
                channel.config_json = {k: v for k, v in merged.items() if k != "last_error"}
        except Exception as exc:
            logger.error("Retell telephony provision failed", tenant_id=str(tenant_id), error=str(exc))
            channel.status = "error"
            tenant_agent.status = "error"
            channel.config_json = {**merged, "last_error": "Retell provisioning failed"}

        await self.db.commit()
        return await self.status(tenant_id)

    async def status(self, tenant_id: UUID) -> dict[str, Any]:
        channel = await self.get_or_create_channel(tenant_id)
        agent = await self.get_or_create_retell_agent(tenant_id)
        rule = await self.get_or_create_escalation_rule(tenant_id)
        usage = await self.current_usage(tenant_id)
        calls = await self.recent_calls(tenant_id)
        return {
            "status": channel.status,
            "channel": {
                "channelType": channel.channel_type,
                "provider": channel.provider,
                "config": channel.config_json or {},
            },
            "retellAgent": {
                "agentId": agent.retell_agent_id,
                "phoneNumber": agent.retell_phone_number,
                "humanEscalationPhone": agent.human_escalation_phone,
                "fallbackEmail": agent.fallback_email,
                "webhookUrl": agent.webhook_url,
                "status": agent.status,
                "lastSyncedAt": agent.last_synced_at.isoformat() if agent.last_synced_at else None,
            },
            "routing": {
                "humanEscalationPhone": rule.human_escalation_phone or agent.human_escalation_phone,
                "fallbackEmail": rule.fallback_email or agent.fallback_email,
                "businessHours": rule.business_hours or {},
                "enabled": rule.enabled,
            },
            "usage": usage,
            "recentCalls": calls,
        }

    async def update_config(self, tenant_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        channel = await self.get_or_create_channel(tenant_id)
        agent = await self.get_or_create_retell_agent(tenant_id)
        rule = await self.get_or_create_escalation_rule(tenant_id)

        if "status" in payload and payload["status"] in {"active", "disabled", "provisioning", "error"}:
            channel.status = payload["status"]
            agent.status = payload["status"]
        if "human_escalation_phone" in payload:
            agent.human_escalation_phone = clean_phone(payload.get("human_escalation_phone")) or None
            rule.human_escalation_phone = agent.human_escalation_phone
        if "fallback_email" in payload:
            agent.fallback_email = (payload.get("fallback_email") or "").strip() or None
            rule.fallback_email = agent.fallback_email
        if "business_hours" in payload and isinstance(payload["business_hours"], dict):
            rule.business_hours = payload["business_hours"]
        if "trigger_keywords" in payload and isinstance(payload["trigger_keywords"], list):
            rule.trigger_keywords = payload["trigger_keywords"]
        if "retell_phone_number" in payload:
            agent.retell_phone_number = clean_phone(payload.get("retell_phone_number")) or None

        config_json = dict(channel.config_json or {})
        config_json.update({k: v for k, v in payload.items() if k not in {"status"}})
        channel.config_json = config_json
        await self.db.commit()
        return await self.status(tenant_id)

    async def test_call(self, tenant_id: UUID, to_number: str) -> dict[str, Any]:
        agent = await self.get_or_create_retell_agent(tenant_id)
        if not agent.retell_agent_id:
            raise ValueError("AI Telephony is not provisioned")
        if not agent.retell_phone_number:
            raise ValueError("Retell phone number is not configured")
        clean_to = clean_phone(to_number)
        if not clean_to.startswith("+"):
            raise ValueError("Enter phone number in E.164 format, e.g. +15551234567")
        data = await retell_service.create_phone_call(
            agent_id=agent.retell_agent_id,
            from_number=agent.retell_phone_number,
            to_number=clean_to,
            metadata={"tenant_id": str(tenant_id), "channel_type": CHANNEL_TYPE, "source": "test_call"},
        )
        return {"ok": True, "providerCallId": data.get("call_id"), "toNumber": clean_to}

    async def handle_tool_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = await self.resolve_tenant_id(payload)
        message = str(payload.get("message") or payload.get("transcript_chunk") or payload.get("input") or "")
        brain = OmniwebBrainService(self.db)
        response = await brain.run(
            BrainRequest(
                tenant_id=tenant_id,
                channel_type=CHANNEL_TYPE,
                user_message=message,
                metadata={"provider": PROVIDER, **payload},
            )
        )
        return {
            "response_text": response.response_text,
            "actions": response.actions,
            "escalation": response.escalation,
            "lead_fields": response.lead_fields,
        }

    async def handle_call_start(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = await self.resolve_tenant_id(payload)
        call_id = self._provider_call_id(payload)
        log = await self._get_or_create_call_log(tenant_id, call_id)
        log.retell_agent_id = payload.get("agent_id") or payload.get("retell_agent_id") or log.retell_agent_id
        log.caller_phone = payload.get("from_number") or payload.get("caller_phone") or log.caller_phone
        log.direction = payload.get("direction") or "inbound"
        log.started_at = self._parse_timestamp(payload.get("started_at")) or log.started_at or utcnow()
        log.metadata_json = {**(log.metadata_json or {}), "start_payload": payload}
        await self.db.commit()
        return {"ok": True, "tenant_id": str(tenant_id), "provider_call_id": call_id}

    async def handle_call_end(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = await self.resolve_tenant_id(payload)
        call_id = self._provider_call_id(payload)
        log = await self._get_or_create_call_log(tenant_id, call_id)
        transcript = payload.get("transcript") or payload.get("transcript_object") or []
        log.transcript = transcript if isinstance(transcript, list) else [{"speaker": "caller", "text": str(transcript)}]
        log.summary = payload.get("summary") or transcript_to_text(log.transcript)[:500] or None
        log.outcome = payload.get("outcome") or payload.get("disconnection_reason")
        log.ended_at = self._parse_timestamp(payload.get("ended_at")) or utcnow()
        if payload.get("duration_seconds") is not None:
            log.duration_seconds = int(float(payload["duration_seconds"]))
        elif log.started_at and log.ended_at:
            log.duration_seconds = max(0, int((log.ended_at - log.started_at).total_seconds()))
        log.escalation_triggered = bool(payload.get("escalation_triggered") or log.escalation_triggered)
        log.metadata_json = {**(log.metadata_json or {}), "end_payload": payload}
        await self._meter_usage(tenant_id, log.duration_seconds or 0)
        await self.db.commit()
        return {"ok": True, "tenant_id": str(tenant_id), "provider_call_id": call_id}

    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = str(payload.get("event") or payload.get("type") or "").lower()
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if "start" in event:
            return await self.handle_call_start(data)
        if "end" in event or "complete" in event or "analyzed" in event:
            return await self.handle_call_end(data)
        if "tool" in event:
            return await self.handle_tool_call(data)
        return {"ok": True, "ignored": True, "event": event}

    async def resolve_tenant_id(self, payload: dict[str, Any]) -> UUID:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        if metadata.get("tenant_id"):
            return UUID(str(metadata["tenant_id"]))
        if payload.get("tenant_id"):
            return UUID(str(payload["tenant_id"]))

        agent_id = payload.get("agent_id") or payload.get("retell_agent_id") or payload.get("override_agent_id")
        phone = clean_phone(payload.get("to_number") or payload.get("from_number") or payload.get("phone_number"))

        query = select(TenantRetellAgent)
        if agent_id:
            result = await self.db.execute(query.where(TenantRetellAgent.retell_agent_id == str(agent_id)))
            agent = result.scalar_one_or_none()
            if agent:
                return agent.tenant_id
        if phone:
            result = await self.db.execute(query.where(TenantRetellAgent.retell_phone_number == phone))
            agent = result.scalar_one_or_none()
            if agent:
                return agent.tenant_id
        raise ValueError("Unable to resolve tenant for Retell event")

    async def recent_calls(self, tenant_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(TenantCallLog)
            .where(TenantCallLog.tenant_id == tenant_id)
            .order_by(desc(TenantCallLog.created_at))
            .limit(limit)
        )
        return [
            {
                "id": str(call.id),
                "callerPhone": call.caller_phone,
                "durationSeconds": call.duration_seconds,
                "summary": call.summary,
                "outcome": call.outcome,
                "escalationTriggered": call.escalation_triggered,
                "createdAt": call.created_at.isoformat(),
            }
            for call in result.scalars().all()
        ]

    async def current_usage(self, tenant_id: UUID) -> dict[str, Any]:
        start, _ = month_bounds()
        result = await self.db.execute(
            select(TenantUsageMetering).where(
                TenantUsageMetering.tenant_id == tenant_id,
                TenantUsageMetering.channel_type == CHANNEL_TYPE,
                TenantUsageMetering.period_start == start,
            )
        )
        usage = result.scalar_one_or_none()
        if not usage:
            client_result = await self.db.execute(select(Client.plan).where(Client.id == tenant_id))
            plan = client_result.scalar_one_or_none() or "starter"
            return {
                "callsUsed": 0,
                "minutesUsed": 0,
                "planLimitMinutes": PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"]),
                "overageMinutes": 0,
                "providerCostEstimate": 0,
                "subscriberBilledUsage": 0,
            }
        return {
            "callsUsed": usage.calls_used,
            "minutesUsed": usage.minutes_used,
            "planLimitMinutes": usage.plan_limit_minutes,
            "overageMinutes": usage.overage_minutes,
            "providerCostEstimate": usage.provider_cost_estimate,
            "subscriberBilledUsage": usage.subscriber_billed_usage,
        }

    async def _get_agent_config(self, tenant_id: UUID) -> AgentConfig:
        result = await self.db.execute(select(AgentConfig).where(AgentConfig.client_id == tenant_id))
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError("No agent configuration for tenant")
        return config

    async def _first_retell_phone_number(self) -> str | None:
        if not settings.RETELL_API_KEY:
            return None
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{retell_service.RETELL_API_BASE}/list-phone-numbers",
                headers={"Authorization": f"Bearer {settings.RETELL_API_KEY}"},
            )
            response.raise_for_status()
            data = response.json()
        if isinstance(data, list) and data:
            return clean_phone(data[0].get("phone_number"))
        return None

    async def _create_or_prepare_retell_agent(
        self,
        config: AgentConfig,
        tenant_agent: TenantRetellAgent,
    ) -> str | None:
        existing_agent_id = config.retell_agent_id or settings.RETELL_LANDING_AGENT_ID
        if existing_agent_id:
            await self._sync_retell_agent(config, tenant_agent)
            return existing_agent_id

        if not settings.RETELL_API_KEY:
            return None

        payload = self._retell_agent_payload(config, tenant_agent)
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{retell_service.RETELL_API_BASE}/create-agent",
                headers={"Authorization": f"Bearer {settings.RETELL_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code == 404:
            # Some Retell accounts provision agents manually. In that case keep
            # the configured landing agent as the tenant agent until replaced.
            return config.retell_agent_id or settings.RETELL_LANDING_AGENT_ID or None
        response.raise_for_status()
        data = response.json()
        return data.get("agent_id") or data.get("retell_agent_id")

    async def _sync_retell_agent(self, config: AgentConfig, tenant_agent: TenantRetellAgent) -> None:
        if not tenant_agent.retell_agent_id:
            return
        payload = self._retell_agent_payload(config, tenant_agent)
        try:
            await retell_service.patch_agent(tenant_agent.retell_agent_id, payload)
        except Exception as exc:
            logger.warning("Retell agent patch failed", retell_agent_id=tenant_agent.retell_agent_id, error=str(exc))

    def _retell_agent_payload(self, config: AgentConfig, tenant_agent: TenantRetellAgent) -> dict[str, Any]:
        return {
            "agent_name": config.agent_name or "Omniweb AI Telephony",
            "response_engine": {
                "type": "custom-llm",
                "llm_websocket_url": f"{settings.ENGINE_BASE_URL.rstrip('/').replace('https://', 'wss://').replace('http://', 'ws://')}/api/retell/tool-call",
            },
            "language": retell_service.map_locale_to_retell_language(config.supported_languages or ["en"]),
            "voice_id": config.voice_id or settings.ELEVENLABS_DEFAULT_VOICE_ID,
            "begin_message": config.agent_greeting,
            "general_prompt": compose_channel_prompt(config, CHANNEL_TYPE),
            "webhook_url": tenant_agent.webhook_url,
            "metadata": {
                "tenant_id": str(config.client_id),
                "channel_type": CHANNEL_TYPE,
                "human_escalation_phone": tenant_agent.human_escalation_phone or config.handoff_phone,
                "fallback_email": tenant_agent.fallback_email or config.handoff_email,
            },
        }

    async def _get_or_create_call_log(self, tenant_id: UUID, provider_call_id: str | None) -> TenantCallLog:
        if provider_call_id:
            result = await self.db.execute(
                select(TenantCallLog).where(
                    TenantCallLog.provider == PROVIDER,
                    TenantCallLog.provider_call_id == provider_call_id,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing
        log = TenantCallLog(
            tenant_id=tenant_id,
            provider=PROVIDER,
            provider_call_id=provider_call_id,
            metadata_json={},
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def _meter_usage(self, tenant_id: UUID, duration_seconds: int) -> None:
        start, end = month_bounds()
        result = await self.db.execute(
            select(TenantUsageMetering).where(
                TenantUsageMetering.tenant_id == tenant_id,
                TenantUsageMetering.channel_type == CHANNEL_TYPE,
                TenantUsageMetering.period_start == start,
            )
        )
        usage = result.scalar_one_or_none()
        if not usage:
            client_result = await self.db.execute(select(Client.plan).where(Client.id == tenant_id))
            plan = client_result.scalar_one_or_none() or "starter"
            usage = TenantUsageMetering(
                tenant_id=tenant_id,
                channel_type=CHANNEL_TYPE,
                period_start=start,
                period_end=end,
                plan_limit_minutes=PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"]),
            )
            self.db.add(usage)
        minutes = round(max(duration_seconds, 0) / 60, 2)
        usage.calls_used += 1
        usage.minutes_used = round((usage.minutes_used or 0) + minutes, 2)
        usage.overage_minutes = max(0.0, round(usage.minutes_used - usage.plan_limit_minutes, 2))
        usage.provider_cost_estimate = round(usage.minutes_used * RETELL_PROVIDER_COST_PER_MINUTE, 2)
        usage.subscriber_billed_usage = round(usage.overage_minutes * SUBSCRIBER_BILLED_PER_MINUTE, 2)

    def _provider_call_id(self, payload: dict[str, Any]) -> str | None:
        return payload.get("call_id") or payload.get("provider_call_id") or payload.get("retell_call_id")

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            raw = float(value)
            if raw > 10_000_000_000:
                raw = raw / 1000
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None


def verify_retell_signature(raw_body: bytes, signature: str | None) -> bool:
    if not settings.RETELL_WEBHOOK_SECRET:
        return True
    if not signature:
        return False
    expected = hmac.new(settings.RETELL_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected) or hmac.compare_digest(f"sha256={expected}", signature)

"""OpenTelemetry-compatible Correlation & Telemetry for Omniweb Contact Center.

Maintains request/session correlation context across:
- LiveKit real-time voice sessions
- Conversation Gateway
- LangGraph State Machine
- Specialist Agents
- DeepAgents Delegation
- Tool & Policy Execution
"""
from __future__ import annotations

import contextvars
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Correlation Context Variables ───────────────────────────────────────────

_tenant_id_ctx = contextvars.ContextVar[str | None]("tenant_id", default=None)
_session_id_ctx = contextvars.ContextVar[str | None]("session_id", default=None)
_call_id_ctx = contextvars.ContextVar[str | None]("call_id", default=None)
_interaction_id_ctx = contextvars.ContextVar[str | None]("interaction_id", default=None)
_workflow_id_ctx = contextvars.ContextVar[str | None]("workflow_id", default=None)
_active_agent_ctx = contextvars.ContextVar[str | None]("active_agent", default=None)
_correlation_id_ctx = contextvars.ContextVar[str | None]("correlation_id", default=None)


@dataclass
class CorrelationContext:
    tenant_id: str | None = None
    session_id: str | None = None
    call_id: str | None = None
    interaction_id: str | None = None
    workflow_id: str | None = None
    active_agent: str | None = None
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}")
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_current_correlation() -> CorrelationContext:
    """Retrieve the active correlation context from contextvars."""
    return CorrelationContext(
        tenant_id=_tenant_id_ctx.get(),
        session_id=_session_id_ctx.get(),
        call_id=_call_id_ctx.get(),
        interaction_id=_interaction_id_ctx.get(),
        workflow_id=_workflow_id_ctx.get(),
        active_agent=_active_agent_ctx.get(),
        correlation_id=_correlation_id_ctx.get() or f"corr_{uuid.uuid4().hex[:12]}",
    )


@contextmanager
def correlation_scope(
    *,
    tenant_id: str | None = None,
    session_id: str | None = None,
    call_id: str | None = None,
    interaction_id: str | None = None,
    workflow_id: str | None = None,
    active_agent: str | None = None,
    correlation_id: str | None = None,
) -> Generator[CorrelationContext, None, None]:
    """Synchronous context manager for binding correlation IDs."""
    corr_id = correlation_id or _correlation_id_ctx.get() or f"corr_{uuid.uuid4().hex[:12]}"

    tokens = [
        _tenant_id_ctx.set(tenant_id or _tenant_id_ctx.get()),
        _session_id_ctx.set(session_id or _session_id_ctx.get()),
        _call_id_ctx.set(call_id or _call_id_ctx.get()),
        _interaction_id_ctx.set(interaction_id or _interaction_id_ctx.get()),
        _workflow_id_ctx.set(workflow_id or _workflow_id_ctx.get()),
        _active_agent_ctx.set(active_agent or _active_agent_ctx.get()),
        _correlation_id_ctx.set(corr_id),
    ]

    try:
        yield get_current_correlation()
    finally:
        _tenant_id_ctx.reset(tokens[0])
        _session_id_ctx.reset(tokens[1])
        _call_id_ctx.reset(tokens[2])
        _interaction_id_ctx.reset(tokens[3])
        _workflow_id_ctx.reset(tokens[4])
        _active_agent_ctx.reset(tokens[5])
        _correlation_id_ctx.reset(tokens[6])


@asynccontextmanager
async def async_correlation_scope(
    *,
    tenant_id: str | None = None,
    session_id: str | None = None,
    call_id: str | None = None,
    interaction_id: str | None = None,
    workflow_id: str | None = None,
    active_agent: str | None = None,
    correlation_id: str | None = None,
) -> AsyncGenerator[CorrelationContext, None]:
    """Asynchronous context manager for binding correlation IDs."""
    with correlation_scope(
        tenant_id=tenant_id,
        session_id=session_id,
        call_id=call_id,
        interaction_id=interaction_id,
        workflow_id=workflow_id,
        active_agent=active_agent,
        correlation_id=correlation_id,
    ) as ctx:
        yield ctx


class MetricTracker:
    """Lightweight in-memory and OpenTelemetry-ready metrics recorder."""

    @staticmethod
    def record_turn_latency(
        *,
        stage: str,  # e.g., "stt", "intent_classification", "agent_reasoning", "tool_exec", "tts"
        duration_ms: float,
        agent: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        corr = get_current_correlation()
        logger.info(
            f"[Metric] Turn Latency: {stage}={duration_ms:.1f}ms",
            extra={
                "metric_type": "turn_latency",
                "stage": stage,
                "duration_ms": duration_ms,
                "agent": agent or corr.active_agent,
                "tenant_id": tenant_id or corr.tenant_id,
                "correlation_id": corr.correlation_id,
            },
        )

    @staticmethod
    def record_cost(
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        estimated_usd: float,
    ) -> None:
        corr = get_current_correlation()
        logger.info(
            f"[Metric] LLM Cost: model={model}, tokens={input_tokens + output_tokens}, est_usd=${estimated_usd:.5f}",
            extra={
                "metric_type": "llm_cost",
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_usd": estimated_usd,
                "tenant_id": corr.tenant_id,
                "correlation_id": corr.correlation_id,
            },
        )

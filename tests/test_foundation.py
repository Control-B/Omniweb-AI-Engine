"""Unit tests for Phase 1 Foundation: Config, Telemetry, Model Routing, and Tool Registry."""
import pytest
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.telemetry import correlation_scope, get_current_correlation
from app.orchestration.model_router import ModelRouter, ModelTier, get_model_router
from app.tools.base import ToolRiskLevel
from app.tools.registry import get_tool_registry


def test_settings_feature_flags():
    """Verify that contact center feature flags and settings are loaded properly."""
    settings = get_settings()
    assert settings.ENABLE_LANGGRAPH is True
    assert settings.ENABLE_LIVEKIT is True
    assert settings.ENABLE_ADK is True
    assert settings.ENABLE_DEEP_AGENTS is True
    assert settings.DEFAULT_INTENT_MODEL == "gemini-2.0-flash"
    assert settings.HIGH_RISK_CREDIT_THRESHOLD == 50.0


def test_telemetry_correlation_scope():
    """Verify correlation IDs and tenant contexts propagate correctly through contextvars."""
    tenant = "tenant_test_123"
    session = "sess_456"
    call = "call_789"

    with correlation_scope(tenant_id=tenant, session_id=session, call_id=call, active_agent="receptionist"):
        ctx = get_current_correlation()
        assert ctx.tenant_id == tenant
        assert ctx.session_id == session
        assert ctx.call_id == call
        assert ctx.active_agent == "receptionist"
        assert ctx.correlation_id.startswith("corr_")

    # Scope reset verification
    after_ctx = get_current_correlation()
    assert after_ctx.tenant_id is None


@pytest.mark.asyncio
async def test_model_router_generation():
    """Verify ModelRouter generates text and structured schemas."""
    router = get_model_router()
    
    # Text generation
    resp = await router.generate_text("Hello AI", tier=ModelTier.FAST_INTENT)
    assert resp.content is not None
    assert resp.duration_ms >= 0

    # Structured generation
    class ClassificationResult(BaseModel):
        intent: str
        urgency: str

    struct_res = await router.generate_structured("I need help with my bill", schema=ClassificationResult)
    assert isinstance(struct_res, ClassificationResult)
    assert struct_res.intent is not None


@pytest.mark.asyncio
async def test_tool_registry_rbac_and_validation():
    """Verify tool discovery, schema validation, RBAC checks, and HITL high-risk behavior."""
    registry = get_tool_registry()

    # 1. Discovery
    lookup_tool = registry.get("lookup_customer")
    assert lookup_tool is not None

    # 2. Agent RBAC allowlist
    receptionist_tools = registry.get_tools_for_agent("receptionist")
    receptionist_tool_names = [t.name for t in receptionist_tools]
    assert "lookup_customer" in receptionist_tool_names
    assert "create_lead" in receptionist_tool_names
    # request_refund should NOT be permitted for receptionist
    assert "request_refund" not in receptionist_tool_names

    # 3. Unauthorized tool execution attempt
    denied_res = await registry.execute_tool(
        "request_refund",
        {"customer_id": "c1", "invoice_id": "i1", "amount": 100.0, "reason": "test"},
        tenant_id="t1",
        agent_name="receptionist",
    )
    assert denied_res.success is False
    assert "not authorized" in denied_res.error

    # 4. Standard tool execution
    lookup_res = await registry.execute_tool(
        "lookup_customer",
        {"phone_number": "+15551234567"},
        tenant_id="t1",
        agent_name="receptionist",
    )
    assert lookup_res.success is True
    assert lookup_res.data["found"] is True

    # 5. High-Risk tool execution (Triggers Human-in-the-Loop!)
    refund_res = await registry.execute_tool(
        "request_refund",
        {"customer_id": "c1", "invoice_id": "INV-123", "amount": 150.0, "reason": "Service outage"},
        tenant_id="t1",
        agent_name="billing",
    )
    assert refund_res.requires_approval is True
    assert refund_res.approval_id is not None
    assert refund_res.data["status"] == "pending_human_approval"

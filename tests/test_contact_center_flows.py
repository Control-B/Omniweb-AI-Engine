"""End-to-End Workflow Tests for Omniweb Agentic AI Contact Center.

Validates all 7 portfolio scenarios:
1. Scenario 1: Normal Reception & General Discovery
2. Scenario 2: Appointment Booking Workflow
3. Scenario 3: Billing Investigation & Invoicing Review
4. Scenario 4: Complex Investigation via DeepAgents
5. Scenario 5: Human-in-the-Loop High-Risk Approval Gate
6. Scenario 6: Human Escalation with Context Preservation
7. Scenario 7: Sales Lead Qualification & CRM Sync
"""
import pytest

from app.orchestration.deepagents.service import get_deep_agent_service
from app.orchestration.langgraph.graph import run_contact_center_turn
from app.orchestration.langgraph.state import create_initial_state
from app.policies.engine import PolicyDecision, get_policy_engine
from app.tools.registry import get_tool_registry


@pytest.mark.asyncio
async def test_scenario_1_normal_reception():
    """Scenario 1: Caller asks general questions -> Receptionist handles with knowledge lookup."""
    state = create_initial_state(
        tenant_id="tenant_demo_1",
        initial_message="Hi, what are your operating hours?",
    )
    result = await run_contact_center_turn(state)
    assert result["active_agent"] == "receptionist"
    assert result["response_text"] is not None
    assert len(result["messages"]) == 2  # user + assistant


@pytest.mark.asyncio
async def test_scenario_2_appointment_scheduling():
    """Scenario 2: Caller books an appointment -> Router activates scheduling agent and checks availability."""
    state = create_initial_state(
        tenant_id="tenant_demo_1",
        caller_phone="+15551112233",
        initial_message="I'd like to book an appointment for tomorrow afternoon.",
    )
    result = await run_contact_center_turn(state)
    assert result["active_agent"] == "scheduling"
    assert result["workflow_name"] == "appointment_booking"
    assert "check_availability" in result["tool_results"]


@pytest.mark.asyncio
async def test_scenario_3_billing_investigation():
    """Scenario 3: Caller inquires about recent bill -> Router activates billing agent and retrieves invoices."""
    state = create_initial_state(
        tenant_id="tenant_demo_1",
        customer_id="cust_849201",
        initial_message="Can you explain my last invoice of $299?",
    )
    result = await run_contact_center_turn(state)
    assert result["active_agent"] == "billing"
    assert "get_invoices" in result["tool_results"]
    assert len(result["tool_results"]["get_invoices"]["invoices"]) > 0


@pytest.mark.asyncio
async def test_scenario_4_deepagents_delegation():
    """Scenario 4: Complex multi-month historical billing dispute delegated to DeepAgents."""
    deepagents = get_deep_agent_service()
    report = await deepagents.investigate_billing_dispute(
        customer_id="cust_849201",
        dispute_reason="Charge discrepancy across past 6 months",
        months_back=6,
        tenant_id="tenant_demo_1",
    )
    assert report.task_type == "billing_dispute_audit"
    assert report.status == "completed"
    assert len(report.subtasks_executed) == 2
    assert "recommended_action" in report.model_dump()


@pytest.mark.asyncio
async def test_scenario_5_hitl_high_risk_approval():
    """Scenario 5: Agent proposes $150 refund -> Policy Engine flags HIGH_RISK -> Enters PENDING_APPROVAL."""
    policy_engine = get_policy_engine()
    registry = get_tool_registry()

    # Policy check
    eval_res = policy_engine.evaluate_action(
        action="request_refund",
        params={"amount": 150.0},
        tenant_id="tenant_demo_1",
    )
    assert eval_res.decision == PolicyDecision.REQUIRE_APPROVAL
    assert eval_res.rule_id == "RULE_REFUND_LIMIT_EXCEEDED"

    # Execution check through tool registry
    tool_res = await registry.execute_tool(
        "request_refund",
        {"customer_id": "c1", "invoice_id": "INV-001", "amount": 150.0, "reason": "Downtime credit"},
        tenant_id="tenant_demo_1",
        agent_name="billing",
    )
    assert tool_res.requires_approval is True
    assert tool_res.data["status"] == "pending_human_approval"


@pytest.mark.asyncio
async def test_scenario_6_human_escalation():
    """Scenario 6: Angry caller asks for a human -> Router triggers escalation agent with context preserved."""
    state = create_initial_state(
        tenant_id="tenant_demo_1",
        caller_phone="+15559998877",
        initial_message="This is completely unacceptable, let me speak to a human manager right now!",
    )
    result = await run_contact_center_turn(state)
    assert result["active_agent"] == "escalation"
    assert result["workflow_name"] == "human_escalation"
    assert result["caller_phone"] == "+15559998877"


@pytest.mark.asyncio
async def test_scenario_7_sales_conversion():
    """Scenario 7: Inbound prospect inquiries about pricing -> Sales agent qualifies lead and captures CRM record."""
    state = create_initial_state(
        tenant_id="tenant_demo_1",
        initial_message="We have 25 support reps and want to switch to your AI contact center. What is pricing?",
    )
    result = await run_contact_center_turn(state)
    assert result["active_agent"] == "sales"
    assert result["workflow_name"] == "sales_conversion"

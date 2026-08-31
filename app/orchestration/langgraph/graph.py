"""LangGraph Contact Center State Machine Compilation & Runner."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.core.telemetry import async_correlation_scope
from app.orchestration.langgraph.nodes import (
    classifier_node,
    finalizer_node,
    router_node,
    specialist_agent_node,
    tool_execution_node,
)
from app.orchestration.langgraph.state import ContactCenterState, create_initial_state

logger = get_logger(__name__)


class ContactCenterOrchestrator:
    """Stateful orchestrator executing the contact center state graph."""

    async def process_turn(self, state: ContactCenterState) -> ContactCenterState:
        """Process a single conversational turn through the durable state machine."""
        async with async_correlation_scope(
            tenant_id=state.get("tenant_id"),
            session_id=state.get("session_id"),
            workflow_id=state.get("workflow_name"),
            active_agent=state.get("active_agent"),
        ):
            logger.info(
                f"[ContactCenterOrchestrator] Turn started for session {state.get('session_id')}"
            )

            # Node 1: Classification (NLU, Intent, Sentiment, Entities)
            classification_update = await classifier_node(state)
            current_state: ContactCenterState = {**state, **classification_update}  # type: ignore

            # Node 2: Routing (Select specialist agent & workflow)
            routing_update = await router_node(current_state)
            current_state = {**current_state, **routing_update}  # type: ignore

            # Node 3: Specialist Agent Execution (Reasoning & Tool Selection)
            agent_update = await specialist_agent_node(current_state)
            current_state = {**current_state, **agent_update}  # type: ignore

            # Node 4: Tool Execution (Execute tools through registry & check HITL)
            tool_update = await tool_execution_node(current_state)
            current_state = {**current_state, **tool_update}  # type: ignore

            # Node 5: Finalizer (Assemble response & append to transcript)
            final_update = await finalizer_node(current_state)
            current_state = {**current_state, **final_update}  # type: ignore

            logger.info(
                f"[ContactCenterOrchestrator] Turn completed. Active Agent: {current_state.get('active_agent')}, Intent: {current_state.get('intent')}"
            )
            return current_state


_orchestrator = ContactCenterOrchestrator()


async def run_contact_center_turn(state: ContactCenterState) -> ContactCenterState:
    """Entrypoint function to run a conversational turn through the state machine."""
    return await _orchestrator.process_turn(state)

"""Enterprise Tool Registry for Omniweb Contact Center.

Manages:
- Tool registration and discovery
- Schema validation via Pydantic
- Agent-level RBAC and tool permission allowlists
- Risk evaluation and Human-in-the-Loop triggers
- Execution timing and immutable audit trail logging
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import ValidationError

from app.core.logging import get_logger
from app.core.telemetry import MetricTracker, get_current_correlation
from app.tools.base import BaseTool, ToolResult, ToolRiskLevel

logger = get_logger(__name__)


class ToolPermissionDenied(Exception):
    """Raised when an agent attempts to invoke a tool outside its allowed boundaries."""
    pass


class ToolRegistry:
    """Central registry of executable enterprise tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool registration: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} [{tool.category.value}] (risk={tool.risk_level.value})")

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tools_for_agent(self, agent_name: str) -> list[BaseTool]:
        """Return all tools permitted for a specific specialist agent."""
        permitted: list[BaseTool] = []
        for tool in self._tools.values():
            # If no restrictions specified, tool is available to all, otherwise check allowlist
            if not tool.allowed_agents or agent_name in tool.allowed_agents or "all" in tool.allowed_agents:
                permitted.append(tool)
        return permitted

    def get_schemas_for_agent(self, agent_name: str) -> list[dict[str, Any]]:
        """Return LLM function calling schemas permitted for the given agent."""
        return [tool.get_json_schema() for tool in self.get_tools_for_agent(agent_name)]

    async def execute_tool(
        self,
        name: str,
        raw_params: dict[str, Any],
        *,
        tenant_id: str,
        agent_name: str,
        caller_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Validate, authorize, and execute a tool invocation with full auditability."""
        start_time = time.perf_counter()
        corr = get_current_correlation()
        tool = self.get(name)

        if not tool:
            err_msg = f"Tool '{name}' is not registered in the system."
            logger.error(err_msg)
            return ToolResult(success=False, error=err_msg)

        # 1. RBAC Check: Ensure requesting agent is permitted to invoke this tool
        if tool.allowed_agents and agent_name not in tool.allowed_agents and "all" not in tool.allowed_agents:
            err_msg = (
                f"Agent '{agent_name}' is not authorized to invoke tool '{name}'. "
                f"Allowed agents: {tool.allowed_agents}"
            )
            logger.error(err_msg, extra={"tenant_id": tenant_id, "correlation_id": corr.correlation_id})
            return ToolResult(success=False, error=err_msg)

        # 2. Schema Validation via Pydantic
        try:
            validated_params = tool.input_schema.model_validate(raw_params)
        except ValidationError as val_err:
            err_msg = f"Invalid parameters for tool '{name}': {val_err.errors()}"
            logger.error(err_msg)
            return ToolResult(success=False, error=err_msg)

        # 3. High-Risk Evaluation (Human-in-the-Loop check)
        if tool.risk_level == ToolRiskLevel.HIGH_RISK:
            approval_id = f"appr_{uuid.uuid4().hex[:10]}"
            logger.warning(
                f"[HITL Triggered] Tool '{name}' classified as HIGH_RISK. Approval ID: {approval_id}",
                extra={"approval_id": approval_id, "tenant_id": tenant_id, "agent": agent_name},
            )
            return ToolResult(
                success=True,
                requires_approval=True,
                approval_id=approval_id,
                data={
                    "status": "pending_human_approval",
                    "approval_id": approval_id,
                    "tool": name,
                    "proposed_params": validated_params.model_dump(),
                    "message": "This action requires supervisory approval before execution.",
                },
            )

        # 4. Tool Execution
        try:
            result = await tool.execute(
                validated_params,
                tenant_id=tenant_id,
                caller_id=caller_id,
                agent_name=agent_name,
                context=context,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            result.execution_time_ms = duration_ms

            MetricTracker.record_turn_latency(
                stage=f"tool_{name}",
                duration_ms=duration_ms,
                agent=agent_name,
                tenant_id=tenant_id,
            )

            logger.info(
                f"Tool '{name}' executed successfully in {duration_ms:.1f}ms",
                extra={
                    "tool_name": name,
                    "agent": agent_name,
                    "tenant_id": tenant_id,
                    "duration_ms": duration_ms,
                    "correlation_id": corr.correlation_id,
                },
            )
            return result

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"Execution of tool '{name}' failed: {str(exc)}"
            logger.error(err_msg, exc_info=True)
            return ToolResult(
                success=False,
                error=err_msg,
                execution_time_ms=duration_ms,
            )


_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Singleton getter for the global tool registry."""
    return _tool_registry

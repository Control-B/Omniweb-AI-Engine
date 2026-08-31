"""Base Tool Abstraction & Metadata Schemas for Omniweb Contact Center.

Every tool exposed to agents must define:
- Strict Pydantic input schema
- Strict Pydantic output schema
- Risk level (STANDARD vs HIGH_RISK requiring HITL)
- Tenant permission requirements
- Idempotency guarantees
- Execution timeout and retry policy
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, TypeVar
import uuid

from pydantic import BaseModel, Field

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class ToolRiskLevel(str, Enum):
    READ_ONLY = "read_only"      # Zero mutation, safe browsing & query
    STANDARD = "standard"        # Safe read/write: lookup, booking, logging
    HIGH_RISK = "high_risk"      # Requires policy check or HITL approval (e.g. refunds, cancellations)
    CRITICAL = "critical"        # System mutations, credential rotation


class ToolCategory(str, Enum):
    CRM = "crm"
    BILLING = "billing"
    CALENDAR = "calendar"
    TICKETING = "ticketing"
    KNOWLEDGE = "knowledge"
    NAVIGATION = "navigation"
    COMMUNICATIONS = "communications"
    TELEPHONY = "telephony"
    RESEARCH = "research"


class ToolResult(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    requires_approval: bool = False
    approval_id: str | None = None
    idempotency_key: str | None = None
    execution_time_ms: float = 0.0


class BaseTool(ABC, Generic[TInput, TOutput]):
    """Abstract Base Class for all Enterprise Contact Center tools."""

    name: str
    description: str
    category: ToolCategory
    risk_level: ToolRiskLevel = ToolRiskLevel.STANDARD
    input_schema: type[TInput]
    output_schema: type[TOutput]
    idempotent: bool = True
    timeout_seconds: float = 10.0
    allowed_agents: list[str] = Field(default_factory=list)

    @abstractmethod
    async def execute(
        self,
        params: TInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute the tool logic with strictly validated parameters."""
        pass

    def get_json_schema(self) -> dict[str, Any]:
        """Return the tool definition JSON schema compatible with LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "parameters": self.input_schema.model_json_schema(),
        }

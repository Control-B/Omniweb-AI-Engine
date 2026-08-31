"""Knowledge Base & Enterprise Policy Retrieval Tools for Omniweb Contact Center."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolCategory, ToolResult, ToolRiskLevel
from app.tools.registry import get_tool_registry


class SearchKnowledgeInput(BaseModel):
    query: str = Field(..., description="Natural language search query")
    category: str | None = Field(None, description="Optional category filter (e.g. policy, pricing, troubleshooting, hours)")
    top_k: int = Field(3, description="Maximum number of knowledge chunks to return")


class SearchKnowledgeOutput(BaseModel):
    results: list[dict[str, Any]]
    total_found: int


class SearchKnowledgeTool(BaseTool[SearchKnowledgeInput, SearchKnowledgeOutput]):
    name = "search_knowledge"
    description = "Search tenant-isolated knowledge base articles, company policies, FAQs, and pricing documents."
    category = ToolCategory.KNOWLEDGE
    risk_level = ToolRiskLevel.STANDARD
    input_schema = SearchKnowledgeInput
    output_schema = SearchKnowledgeOutput
    allowed_agents = ["receptionist", "account", "billing", "sales", "support", "scheduling", "retention", "escalation"]

    async def execute(
        self,
        params: SearchKnowledgeInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        # Mock semantic search results with tenant isolation
        mock_chunks = [
            {
                "title": "Refund & Cancellation Policy",
                "content": "Customers are entitled to a full refund within 30 days of initial subscription. After 30 days, billing credits can be approved up to $50 by Tier-1 agents or higher amounts by supervisors.",
                "source": "https://omniweb.ai/terms",
                "similarity_score": 0.94,
            },
            {
                "title": "Operating Hours & Emergency SLAs",
                "content": "Standard support operates Monday through Friday 8:00 AM to 8:00 PM EST. Critical emergency dispatch line is monitored 24/7/365 with sub-60-second response commitments.",
                "source": "https://omniweb.ai/company/status",
                "similarity_score": 0.88,
            },
        ]
        return ToolResult(
            success=True,
            data={"results": mock_chunks, "total_found": len(mock_chunks)},
        )


# Register tools on import
registry = get_tool_registry()
registry.register(SearchKnowledgeTool())

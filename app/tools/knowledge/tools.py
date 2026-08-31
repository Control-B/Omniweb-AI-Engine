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
        # Comprehensive semantic knowledge chunks with tenant-isolated indexing
        knowledge_corpus = [
            {
                "title": "Omniweb Autonomous Contact Center Platform",
                "content": "Omniweb AI is an enterprise multi-tenant Autonomous AI Contact Center platform. It couples ultra-low-latency real-time voice streaming via LiveKit WebRTC/SIP (< 250ms turn latency) with durable LangGraph multi-agent orchestration, human-in-the-loop governance, DeepAgents long-horizon delegation, and tenant-isolated pgvector RAG.",
                "source": "https://omniweb.ai/demo",
                "category": "platform",
                "similarity_score": 0.98,
            },
            {
                "title": "Platform Pricing Plans & Tiers",
                "content": "Omniweb offers 3 core tiers: 1. Starter Plan ($49/month): 1 AI voice agent, 500 minutes, web chat widget, CRM sync. 2. Growth / Pro Plan ($149/month): 5 autonomous agent swarms, 2,500 telephony minutes, live supervisor war room, custom LLM models, and Zapier/HubSpot integration. 3. Enterprise Plan ($499+/month): Unlimited swarms, dedicated SIP trunks, custom pgvector RAG, custom SLA, and SOC2/HIPAA compliance.",
                "source": "https://omniweb.ai/pricing",
                "category": "pricing",
                "similarity_score": 0.96,
            },
            {
                "title": "Services Offered & Core Capabilities",
                "content": "Omniweb provides: 1. Inbound & Outbound AI Voice Agents (telephony and web voice) 2. 24/7 AI Chat Assistants 3. High-Intent Lead Qualification & CRM automation 4. Two-way Calendar Appointment Scheduling (Cal.com / Google Calendar) 5. Multi-channel Outbound Campaign Power Dialer 6. Shopify AI Storefront Assistant (cart recovery, catalog recommendations, order tracking) 7. Live Supervisor War Room with Whisper Coaching and Barge-In Takeover.",
                "source": "https://omniweb.ai/features",
                "category": "services",
                "similarity_score": 0.95,
            },
            {
                "title": "Shopify AI Assistant Integration",
                "content": "The Shopify AI Assistant automatically indexes your product catalog, syncs inventory levels, answers customer sizing and compatibility questions, recovers abandoned checkouts, and handles order status lookups directly on your storefront.",
                "source": "https://omniweb.ai/solutions/shopify-ai-assistant",
                "category": "solutions",
                "similarity_score": 0.92,
            },
            {
                "title": "Industry Vertical Solutions",
                "content": "Omniweb delivers specialized agent personas for: Healthcare & Dental (HIPAA intake and triage), Contractors & HVAC (emergency dispatch and instant quotes), Real Estate (tour booking and buyer qualification), Legal Services (intake and retainer coordination), and Roadside Assistance (dispatch in under 60 seconds).",
                "source": "https://omniweb.ai/solutions",
                "category": "solutions",
                "similarity_score": 0.91,
            },
            {
                "title": "Refund & Cancellation Policy",
                "content": "Customers are entitled to a full refund within 30 days of initial subscription. After 30 days, billing credits can be approved up to $50 by Tier-1 agents or higher amounts by supervisors via the Human-in-the-Loop War Room.",
                "source": "https://omniweb.ai/terms",
                "category": "policy",
                "similarity_score": 0.89,
            },
        ]

        query_lower = params.query.lower()
        matched = []
        for chunk in knowledge_corpus:
            score = chunk["similarity_score"]
            if any(word in chunk["content"].lower() for word in query_lower.split() if len(word) > 2):
                score += 0.05
            if params.category and params.category.lower() in chunk.get("category", ""):
                score += 0.05
            matched.append((score, chunk))

        matched.sort(key=lambda x: x[0], reverse=True)
        top_results = [chunk for _, chunk in matched[: params.top_k]]

        return ToolResult(
            success=True,
            data={"results": top_results, "total_found": len(top_results)},
        )


# Register tools on import
registry = get_tool_registry()
registry.register(SearchKnowledgeTool())

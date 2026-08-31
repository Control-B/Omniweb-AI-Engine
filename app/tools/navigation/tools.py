"""Site Navigation & Service Catalog Discovery Tools for Omniweb Contact Center."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolCategory, ToolResult, ToolRiskLevel
from app.tools.registry import get_tool_registry


class SiteRoute(BaseModel):
    title: str
    path: str
    category: str
    description: str


SITE_DIRECTORY: list[SiteRoute] = [
    # Core & Live Labs
    SiteRoute(title="Interactive Call Center Lab & Live Demo", path="/demo", category="Core", description="Live interactive sandbox testing voice swarms, LiveKit WebRTC, Deepgram STT, and supervisor intervention."),
    SiteRoute(title="Platform Pricing & Plans", path="/pricing", category="Pricing", description="Transparent pricing tiers: Starter ($49/mo), Pro Growth ($149/mo), and Enterprise Scale ($499+/mo)."),
    SiteRoute(title="Get Started / Sign Up", path="/get-started", category="Auth", description="Create an account and deploy your first autonomous AI voice and chat agent in minutes."),
    SiteRoute(title="Live Call Center War Room", path="/dashboard/call-center", category="Dashboard", description="Real-time call center operations dashboard, queue monitoring, agent execution graphs, and supervisor approval queues."),
    SiteRoute(title="Call Logs & Audio Intelligence", path="/dashboard/call-logs", category="Dashboard", description="Dual-channel call transcripts, audio sentiment scoring, resolution rates, and automated follow-ups."),
    SiteRoute(title="Outbound Campaign Power Dialer", path="/dashboard/campaigns", category="Dashboard", description="Automated outbound multi-agent campaigns, dialer schedules, and lead conversion analytics."),
    SiteRoute(title="Widget Installation & Embed", path="/dashboard/widget-install", category="Dashboard", description="One-click embed script installation for website live voice and chat widgets."),
    
    # Feature Verticals
    SiteRoute(title="AI Voice Agents", path="/features/ai-voice-agents", category="Features", description="Sub-250ms latency inbound and outbound voice agents powered by LiveKit and Deepgram Nova-3."),
    SiteRoute(title="AI Chat Assistants", path="/features/ai-chat-assistants", category="Features", description="Website chat assistants that convert visitors into scheduled appointments and qualified leads."),
    SiteRoute(title="Lead Qualification & Automation", path="/features/lead-automation", category="Features", description="Automatic scoring, real-time intent discovery, and instant lead routing to your CRM."),
    SiteRoute(title="Appointment Scheduling", path="/features/appointment-scheduling", category="Features", description="Two-way calendar sync with Cal.com and Google Calendar for frictionless booking."),
    SiteRoute(title="CRM & Tool Integrations", path="/features/crm-integrations", category="Features", description="Native bidirectional integrations with HubSpot, Salesforce, and custom webhooks."),
    SiteRoute(title="Multilingual AI Voice", path="/features/multilingual-ai", category="Features", description="Instant voice translation and conversation in 25+ languages."),
    
    # Solutions & Industries
    SiteRoute(title="Shopify AI Store Assistant", path="/solutions/shopify-ai-assistant", category="Solutions", description="Autonomous ecommerce sales agent that answers catalog questions, checks orders, and recovers abandoned carts."),
    SiteRoute(title="Healthcare & Dental Triage", path="/solutions/healthcare", category="Solutions", description="HIPAA-aware patient intake, after-hours appointment scheduling, and emergency triage."),
    SiteRoute(title="Contractors & Home Services", path="/solutions/contractors", category="Solutions", description="24/7 quote generation, emergency dispatch, and on-call technician routing."),
    SiteRoute(title="Real Estate Buyer Qualification", path="/solutions/real-estate", category="Solutions", description="Property tour scheduling, buyer qualification, and instant MLS listing query matching."),
    SiteRoute(title="Legal & Professional Services", path="/solutions/professional-services", category="Solutions", description="Client intake interviews, consultation fee collections, and conflict checking."),
    SiteRoute(title="Roadside Assistance Dispatch", path="/solutions/roadside-assistance", category="Solutions", description="Rapid emergency geo-location intake and tow truck dispatch under 60 seconds."),
    
    # Resources & Documentation
    SiteRoute(title="Architecture Documentation & ADRs", path="/resources/docs", category="Resources", description="Engineering guides, system architecture diagrams, and Architectural Decision Records."),
    SiteRoute(title="API Reference", path="/resources/api", category="Resources", description="REST API and WebSocket documentation for voice streams and CRM webhooks."),
]


class NavigateSiteInput(BaseModel):
    query: str = Field(..., description="The user's topic of interest or destination (e.g. 'pricing', 'shopify', 'voice demo', 'call center')")
    category: str | None = Field(None, description="Optional category filter (Core, Pricing, Features, Solutions, Dashboard, Resources)")


class NavigateSiteOutput(BaseModel):
    matched_routes: list[dict[str, Any]]
    recommended_path: str
    recommended_title: str
    explanation: str


class NavigateSiteTool(BaseTool[NavigateSiteInput, NavigateSiteOutput]):
    name = "navigate_site"
    description = "Lookup relevant pages, features, and deep-link navigation routes on the Omniweb AI website based on user queries."
    category = ToolCategory.NAVIGATION
    risk_level = ToolRiskLevel.READ_ONLY
    input_schema = NavigateSiteInput
    output_schema = NavigateSiteOutput
    allowed_agents = ["receptionist", "sales", "support", "scheduling", "account", "billing", "retention", "escalation"]

    async def execute(
        self,
        params: NavigateSiteInput,
        *,
        tenant_id: str,
        caller_id: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        query = params.query.lower().strip()
        matched = []

        for route in SITE_DIRECTORY:
            score = 0
            if query in route.path.lower():
                score += 10
            if any(term in route.title.lower() for term in query.split()):
                score += 5
            if any(term in route.description.lower() for term in query.split()):
                score += 3
            if params.category and params.category.lower() in route.category.lower():
                score += 2

            if score > 0:
                matched.append((score, route))

        # Sort by match score
        matched.sort(key=lambda x: x[0], reverse=True)
        top_routes = [r.dict() for _, r in matched[:3]]

        if not top_routes:
            # Fallback to demo or pricing
            default_route = SITE_DIRECTORY[0].dict()
            return ToolResult(
                success=True,
                data={
                    "matched_routes": [default_route],
                    "recommended_path": default_route["path"],
                    "recommended_title": default_route["title"],
                    "explanation": f"Explore our {default_route['title']} at {default_route['path']}",
                },
            )

        best = top_routes[0]
        return ToolResult(
            success=True,
            data={
                "matched_routes": top_routes,
                "recommended_path": best["path"],
                "recommended_title": best["title"],
                "explanation": f"I recommend navigating to '{best['title']}' ({best['path']}): {best['description']}",
            },
        )


# Register tools on import
registry = get_tool_registry()
registry.register(NavigateSiteTool())

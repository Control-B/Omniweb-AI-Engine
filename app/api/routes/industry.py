"""Industry Router — standalone API for industry browsing and tenant onboarding.

Provides a clean public + authenticated API surface for:
  - Browsing available industries with full metadata
  - Comparing industry configurations side-by-side
  - Onboarding flow: pick industry → get recommended config
  - Qualification field discovery for form builders

Extracted from agent_config.py meta endpoints into a dedicated router
to support the dashboard onboarding wizard and public industry catalog.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.services.industry_config import (
    AGENT_MODES,
    get_industry,
    get_qualification_fields,
    get_escalation_triggers,
    get_industry_tools,
    list_industries,
)
from app.services.prompt_engine import compose_system_prompt, compose_greeting
from app.services.tool_registry import get_tool_definitions, list_available_tools
from app.models.models import AgentConfig

logger = get_logger(__name__)
router = APIRouter(prefix="/industries", tags=["industries"])


# ═══════════════════════════════════════════════════════════════════════════════
#  Public Endpoints (no auth — used by landing page, signup wizard)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("")
async def browse_industries() -> dict:
    """List all available industries with summary metadata.

    Used by the onboarding wizard to show industry cards.
    """
    industries = list_industries()
    enriched = []
    for ind in industries:
        full = get_industry(ind["slug"])
        enriched.append({
            "slug": ind["slug"],
            "label": ind["label"],
            "description": ind["description"],
            "default_agent_mode": full.default_agent_mode,
            "qualification_field_count": len(full.qualification_fields),
            "tool_count": len(full.available_tools),
            "guardrail_count": len(full.guardrails),
            "tone": full.tone,
        })
    return {"industries": enriched, "total": len(enriched)}


@router.get("/modes")
async def get_all_agent_modes() -> dict:
    """List all available agent modes with descriptions."""
    return {
        "modes": [
            {
                "slug": slug,
                "label": info["label"],
                "description": info["description"],
                "primary_goal": info["primary_goal"],
            }
            for slug, info in AGENT_MODES.items()
        ]
    }


@router.get("/{industry_slug}")
async def get_industry_detail(industry_slug: str) -> dict:
    """Get full configuration detail for a specific industry.

    Returns qualification fields, guardrails, tools, scoring rubric,
    example greetings, and recommended agent mode.
    """
    config = get_industry(industry_slug)

    # If slug fell back to "general" but caller asked for something else
    if config.slug != industry_slug and industry_slug != "general":
        raise HTTPException(
            404,
            f"Industry '{industry_slug}' not found. "
            f"Use GET /api/industries to see available options.",
        )

    return {
        "slug": config.slug,
        "label": config.label,
        "description": config.description,
        "default_agent_mode": config.default_agent_mode,
        "tone": config.tone,
        "communication_style": config.communication_style,
        "qualification_fields": config.qualification_fields,
        "available_tools": config.available_tools,
        "guardrails": config.guardrails,
        "escalation_triggers": config.escalation_triggers,
        "scoring_rubric": config.scoring_rubric,
        "default_services": config.default_services,
        "example_greetings": config.example_greetings,
        "domain_context": config.domain_context,
    }


@router.get("/{industry_slug}/fields")
async def get_industry_fields(industry_slug: str) -> dict:
    """Get qualification fields for an industry.

    Used by form builders and the dashboard config panel to render
    dynamic field editors.
    """
    fields = get_qualification_fields(industry_slug)
    required = [f for f in fields if f.get("required")]
    optional = [f for f in fields if not f.get("required")]

    return {
        "industry": industry_slug,
        "fields": fields,
        "required_count": len(required),
        "optional_count": len(optional),
        "required_fields": required,
        "optional_fields": optional,
    }


@router.get("/{industry_slug}/tools")
async def get_industry_tools_detail(industry_slug: str) -> dict:
    """Get available tools for an industry with full schemas.

    Used by the admin panel to preview what tools will be attached
    to agents in this industry.
    """
    tool_names = get_industry_tools(industry_slug)
    tool_defs = get_tool_definitions(tool_names)

    return {
        "industry": industry_slug,
        "tools": [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": list(
                    t.get("api_schema", {})
                     .get("request_body", {})
                     .get("properties", {})
                     .keys()
                ),
            }
            for t in tool_defs
        ],
    }


@router.get("/{industry_slug}/escalation-triggers")
async def get_industry_escalation(industry_slug: str) -> dict:
    """Get escalation trigger phrases for an industry."""
    triggers = get_escalation_triggers(industry_slug)
    return {
        "industry": industry_slug,
        "triggers": triggers,
        "count": len(triggers),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Authenticated Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{industry_slug}/preview-prompt")
async def preview_industry_prompt(
    industry_slug: str,
    agent_mode: Optional[str] = Query(None),
    agent_name: str = Query("Alex"),
    business_name: str = Query("Your Business"),
    current_client: dict = Depends(get_current_client),
) -> dict:
    """Preview the system prompt that would be generated for this industry.

    Useful during onboarding to show clients what their agent will say.
    Authenticated because it invokes the prompt engine.
    """
    config = get_industry(industry_slug)
    mode = agent_mode or config.default_agent_mode

    prompt = compose_system_prompt(
        agent_name=agent_name,
        business_name=business_name,
        industry_slug=industry_slug,
        agent_mode=mode,
    )
    greeting = compose_greeting(
        industry_slug=industry_slug,
        agent_mode=mode,
        agent_name=agent_name,
        business_name=business_name,
    )

    return {
        "industry": industry_slug,
        "agent_mode": mode,
        "composed_prompt": prompt,
        "composed_greeting": greeting,
        "prompt_length_chars": len(prompt),
        "greeting_length_chars": len(greeting),
    }


@router.post("/{industry_slug}/compare")
async def compare_industries(
    industry_slug: str,
    compare_to: list[str],
    current_client: dict = Depends(get_current_client),
) -> dict:
    """Compare qualification fields and guardrails across industries.

    Useful for agencies managing multiple verticals to understand
    differences between industry configurations.
    """
    slugs = [industry_slug] + compare_to[:4]  # Max 5 industries
    comparison = []

    for slug in slugs:
        config = get_industry(slug)
        comparison.append({
            "slug": config.slug,
            "label": config.label,
            "default_agent_mode": config.default_agent_mode,
            "qualification_field_count": len(config.qualification_fields),
            "guardrail_count": len(config.guardrails),
            "tool_count": len(config.available_tools),
            "escalation_trigger_count": len(config.escalation_triggers),
            "required_fields": [
                f["name"] for f in config.qualification_fields if f.get("required")
            ],
            "available_tools": config.available_tools,
            "tone": config.tone,
        })

    return {"comparison": comparison}


@router.get("/stats/distribution")
async def industry_distribution(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the distribution of tenants across industries.

    Admin-only: shows how many clients are using each industry.
    """
    if current_client.get("role") != "admin":
        raise HTTPException(403, "Admin access required")

    result = await db.execute(
        select(AgentConfig.industry, func.count(AgentConfig.id))
        .group_by(AgentConfig.industry)
    )
    distribution = {str(row[0]): row[1] for row in result}

    # Enrich with labels
    all_industries = list_industries()
    enriched = []
    for ind in all_industries:
        enriched.append({
            "slug": ind["slug"],
            "label": ind["label"],
            "tenant_count": distribution.get(ind["slug"], 0),
        })

    # Sort by tenant count descending
    enriched.sort(key=lambda x: x["tenant_count"], reverse=True)

    return {
        "distribution": enriched,
        "total_configured": sum(v for v in distribution.values()),
    }

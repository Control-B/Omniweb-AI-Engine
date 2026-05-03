"""SaaS onboarding, trial enforcement, and widget workspace helpers."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AgentConfig, Client, utcnow
from app.services.prompt_engine import compose_system_prompt

PRIMARY_GOAL_AGENT_MODES: dict[str, str] = {
    "capture_leads": "lead_qualifier",
    "answer_customer_questions": "general_assistant",
    "recommend_products": "ecommerce_assistant",
    "book_appointments": "appointment_setter",
    "qualify_prospects": "lead_qualifier",
    "support_existing_customers": "general_assistant",
}

PRIMARY_GOAL_LABELS: dict[str, str] = {
    "capture_leads": "Capture leads",
    "answer_customer_questions": "Answer customer questions",
    "recommend_products": "Recommend products",
    "book_appointments": "Book appointments",
    "qualify_prospects": "Qualify prospects",
    "support_existing_customers": "Support existing customers",
}

ALLOWED_PRIMARY_GOALS = frozenset(PRIMARY_GOAL_AGENT_MODES.keys())


def normalize_website_input(raw: str) -> tuple[str, str]:
    """Return (clean_domain, full_canonical_url) from arbitrary user input."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("Website is required")
    s = re.sub(r"\s+", "", s)
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s.lstrip("/")
    parsed = urlparse(s)
    host = (parsed.netloc or parsed.path or "").split("/")[0].lower()
    if not host:
        raise ValueError("Could not parse website domain")
    host = host.split(":")[0]
    domain = host[4:] if host.startswith("www.") else host
    if not domain or "." not in domain:
        raise ValueError("Enter a valid website domain")
    canonical = f"https://{host}/"
    return domain, canonical


def calculate_trial_remaining(trial_ends_at: datetime | None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if not trial_ends_at:
        return {"days": 0, "hours": 0, "minutes": 0, "isExpired": True}
    end = trial_ends_at if trial_ends_at.tzinfo else trial_ends_at.replace(tzinfo=timezone.utc)
    if end <= now:
        return {"days": 0, "hours": 0, "minutes": 0, "isExpired": True}
    delta = end - now
    total_seconds = int(delta.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return {"days": days, "hours": hours, "minutes": minutes, "isExpired": False}


def client_subscription_allows_widget(client: Client) -> bool:
    if getattr(client, "stripe_subscription_id", None):
        return True
    status = (client.subscription_status or "").lower()
    if status == "active":
        return True
    if status == "trialing":
        if client.trial_ends_at:
            end = client.trial_ends_at
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            return end > datetime.now(timezone.utc)
        return False
    if status in ("expired", "canceled", "past_due"):
        return False
    if client.trial_ends_at is None:
        return True
    end = client.trial_ends_at
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end > datetime.now(timezone.utc)


def default_setup_progress() -> dict[str, bool]:
    return {
        "business_profile_completed": False,
        "ai_agent_configured": False,
        "widget_tested": False,
        "embed_installed": False,
        "subscription_activated": False,
    }


def _slug_industry(industry: str) -> str:
    s = (industry or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:100] if s else "general"


async def get_agent_config_for_client(db: AsyncSession, client_id: UUID) -> AgentConfig | None:
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client_id))
    return result.scalar_one_or_none()


def _default_widget_ui(agent_name: str, theme: str = "#6366f1") -> dict[str, Any]:
    return {
        "saas_ui": {
            "tone": "professional",
            "position": "bottom-right",
            "theme_color": theme,
            "lead_questions": [
                "What brings you to our site today?",
                "How can we best reach you?",
            ],
            "call_to_action": "Chat with us",
            "knowledge_source_url": "",
        }
    }


def _business_instructions_from_onboarding(
    business_name: str,
    industry: str,
    website_url: str,
    goal_key: str,
) -> str:
    goal_label = PRIMARY_GOAL_LABELS.get(goal_key, goal_key.replace("_", " "))
    return (
        f"You represent {business_name} ({industry}). "
        f"Their website is {website_url}. "
        f"Primary objective: {goal_label}. "
        "Be concise, helpful, and drive the visitor toward that objective."
    )


async def apply_saas_onboarding(
    db: AsyncSession,
    client: Client,
    *,
    business_name: str,
    industry: str,
    website_input: str,
    primary_goal: str,
) -> tuple[Client, AgentConfig]:
    if primary_goal not in ALLOWED_PRIMARY_GOALS:
        raise ValueError("Invalid primary goal")
    domain, website_url = normalize_website_input(website_input)
    industry_slug = _slug_industry(industry)
    agent_mode = PRIMARY_GOAL_AGENT_MODES[primary_goal]
    now = utcnow()

    if not client.public_widget_key:
        client.public_widget_key = secrets.token_urlsafe(32)[:48]

    if client.subscription_status != "active" and client.trial_started_at is None:
        client.trial_started_at = now
        client.trial_ends_at = now + timedelta(days=7)
        client.subscription_status = "trialing"

    client.website_url = website_url
    client.primary_goal = primary_goal
    client.saas_widget_status = "active"
    client.onboarding_completed_at = now

    progress = dict(default_setup_progress())
    progress.update(client.setup_progress or {})
    progress["business_profile_completed"] = True
    progress["ai_agent_configured"] = True
    client.setup_progress = progress

    agent = await get_agent_config_for_client(db, client.id)
    agent_name = "Alex"
    welcome = (
        f"Hi — I'm {agent_name} from {business_name}. How can I help you today?"
    )
    business_instructions = _business_instructions_from_onboarding(
        business_name, industry, website_url, primary_goal
    )

    if not agent:
        agent = AgentConfig(
            client_id=client.id,
            agent_name=agent_name,
            agent_greeting=welcome,
            business_name=business_name[:255],
            business_type=industry[:100] if industry else None,
            website_domain=domain[:255],
            industry=industry_slug[:100],
            agent_mode=agent_mode,
            custom_context=business_instructions,
            use_prompt_engine=True,
            widget_config=_default_widget_ui(agent_name),
        )
        agent.system_prompt = compose_system_prompt(
            agent_name=agent.agent_name,
            business_name=agent.business_name,
            industry_slug=agent.industry,
            agent_mode=agent.agent_mode,
            business_type=agent.business_type,
            custom_context=business_instructions,
        )
        db.add(agent)
    else:
        agent.agent_name = agent_name
        agent.agent_greeting = welcome
        agent.business_name = business_name[:255]
        agent.business_type = industry[:100] if industry else agent.business_type
        agent.website_domain = domain[:255]
        agent.industry = industry_slug[:100]
        agent.agent_mode = agent_mode
        agent.custom_context = business_instructions
        agent.use_prompt_engine = True
        wc = dict(agent.widget_config or {})
        wc.update(_default_widget_ui(agent.agent_name))
        agent.widget_config = wc
        agent.system_prompt = compose_system_prompt(
            agent_name=agent.agent_name,
            business_name=agent.business_name,
            industry_slug=agent.industry,
            agent_mode=agent.agent_mode,
            business_type=agent.business_type,
            custom_context=business_instructions,
        )

    await db.commit()
    await db.refresh(client)
    await db.refresh(agent)
    return client, agent


async def resolve_client_by_widget_key(db: AsyncSession, widget_key: str) -> Client | None:
    key = (widget_key or "").strip()
    if not key:
        return None
    result = await db.execute(select(Client).where(Client.public_widget_key == key))
    client = result.scalar_one_or_none()
    if client:
        return client
    result = await db.execute(select(Client).where(Client.embed_code == key))
    return result.scalar_one_or_none()


async def resolve_client_by_public_identifier(db: AsyncSession, identifier: str) -> Client | None:
    """Resolve customer-facing widget identifiers without exposing UUID-only contracts."""
    raw = (identifier or "").strip()
    if not raw:
        return None
    try:
        client = await db.get(Client, UUID(raw))
    except ValueError:
        client = None
    if client:
        return client
    return await resolve_client_by_widget_key(db, raw)


def normalize_public_domain(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"https://{raw.lstrip('/')}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def platform_domain() -> str:
    return normalize_public_domain("https://omniweb.ai")


def is_platform_domain(domain: str | None) -> bool:
    return normalize_public_domain(domain) == platform_domain()


async def resolve_client_by_public_domain(db: AsyncSession, domain: str) -> Client | None:
    """Resolve legacy anonymous widget calls by the embedding website domain."""
    normalized = normalize_public_domain(domain)
    if not normalized:
        return None

    result = await db.execute(
        select(Client)
        .join(AgentConfig, AgentConfig.client_id == Client.id)
        .where(AgentConfig.website_domain == normalized)
        .limit(20)
    )
    candidates = list(result.scalars().all())
    for client in candidates:
        if (
            getattr(client, "widget_enabled", True) is not False
            and (client.saas_widget_status or "active") != "disabled"
            and client_subscription_allows_widget(client)
        ):
            return client
    return candidates[0] if len(candidates) == 1 else None

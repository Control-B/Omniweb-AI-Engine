from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import AgentConfig, Client, Engagement
from app.services.saas_workspace_service import client_subscription_allows_widget, get_agent_config_for_client, normalize_website_input

settings = get_settings()

DEFAULT_WIDGET_COLOR = "#2563eb"
DEFAULT_WIDGET_POSITION = "bottom-right"
DEFAULT_WELCOME_MESSAGE = "Welcome! How can I help you today?"
VALID_WIDGET_POSITIONS = {"bottom-right", "bottom-left"}
VALID_EVENT_TYPES = {
    "widget_loaded",
    "widget_opened",
    "message_sent",
    "lead_captured",
    "voice_started",
    "voice_ended",
}
WIDGET_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "static" / "widget.js"


class WidgetAccessError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 403):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def build_widget_base_url() -> str:
    return (settings.PUBLIC_WIDGET_BASE_URL or settings.APP_BASE_URL or settings.ENGINE_BASE_URL).rstrip("/")


def build_widget_embed_code(public_widget_id: str) -> str:
    return f'<script src="{build_widget_base_url()}/widget.js" data-tenant-id="{public_widget_id}" async></script>'


def ensure_public_widget_id(client: Client) -> str:
    current = (client.public_widget_key or "").strip()
    if current:
        return current
    client.public_widget_key = secrets.token_urlsafe(18)
    return client.public_widget_key


def normalize_domain(input_value: str | None) -> str:
    raw = (input_value or "").strip()
    if not raw:
        return ""
    candidate = raw
    if "://" not in candidate:
        candidate = f"https://{candidate.lstrip('/')}"
    parsed = urlparse(candidate)
    hostname = (parsed.hostname or parsed.path or "").strip().lower().rstrip(".")
    if not hostname:
        return ""
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def normalize_page_url(input_value: str | None) -> str | None:
    raw = (input_value or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            return None
        return parsed.geturl()[:2048]
    except Exception:
        return None


def normalize_allowed_domains(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        domain = normalize_domain(value)
        if domain and domain not in normalized:
            normalized.append(domain)
    return normalized


def equivalent_domains(left: str, right: str) -> bool:
    a = normalize_domain(left)
    b = normalize_domain(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return a == f"www.{b}" or b == f"www.{a}"


def get_primary_domain(client: Client, agent: AgentConfig | None) -> str | None:
    if agent and agent.website_domain:
        domain = normalize_domain(agent.website_domain)
        if domain:
            return domain
    if client.website_url:
        try:
            domain, _ = normalize_website_input(client.website_url)
            return normalize_domain(domain)
        except ValueError:
            normalized = normalize_domain(client.website_url)
            if normalized:
                return normalized
    return None


def get_allowed_domains(client: Client, agent: AgentConfig | None) -> list[str]:
    domains = normalize_allowed_domains(getattr(client, "allowed_domains", []) or [])
    primary = get_primary_domain(client, agent)
    if primary and primary not in domains:
        domains.append(primary)
    return domains


def is_domain_allowed(domain: str, allowed_domains: list[str], primary_domain: str | None) -> bool:
    if not domain:
        return False
    for allowed in allowed_domains:
        if equivalent_domains(domain, allowed):
            return True
    if primary_domain and equivalent_domains(domain, primary_domain):
        return True
    return False


def widget_is_enabled(client: Client) -> bool:
    if getattr(client, "widget_enabled", True) is False:
        return False
    return (client.saas_widget_status or "active") != "disabled"


def get_widget_theme(agent: AgentConfig | None) -> dict[str, Any]:
    widget_config = agent.widget_config if agent and isinstance(agent.widget_config, dict) else {}
    saas_ui = widget_config.get("saas_ui") if isinstance(widget_config, dict) else {}
    return saas_ui if isinstance(saas_ui, dict) else {}


def get_widget_settings_payload(client: Client, agent: AgentConfig | None) -> dict[str, Any]:
    theme = get_widget_theme(agent)
    allowed_domains = get_allowed_domains(client, agent)
    public_widget_id = ensure_public_widget_id(client)
    widget_enabled = widget_is_enabled(client)
    welcome_message = client.widget_welcome_message or (agent.agent_greeting if agent else None) or DEFAULT_WELCOME_MESSAGE
    primary_color = client.widget_primary_color or theme.get("theme_color") or DEFAULT_WIDGET_COLOR
    position = client.widget_position or theme.get("position") or DEFAULT_WIDGET_POSITION
    if position not in VALID_WIDGET_POSITIONS:
        position = DEFAULT_WIDGET_POSITION

    return {
        "publicWidgetId": public_widget_id,
        "embedCode": build_widget_embed_code(public_widget_id),
        "scriptUrl": f"{build_widget_base_url()}/widget.js",
        "allowedDomains": allowed_domains,
        "widgetEnabled": widget_enabled,
        "widgetInstalled": bool(client.widget_installed),
        "widgetLastSeenAt": serialize_datetime(client.widget_last_seen_at),
        "widgetPrimaryColor": primary_color,
        "widgetPosition": position,
        "widgetWelcomeMessage": welcome_message,
        "voiceEnabled": bool(client.voice_enabled),
        "businessName": (agent.business_name if agent and agent.business_name else client.name) or "Omniweb",
        "agentMode": (agent.agent_mode if agent and agent.agent_mode else "general_lead_gen"),
    }


def build_public_widget_config(client: Client, agent: AgentConfig | None) -> dict[str, Any]:
    settings_payload = get_widget_settings_payload(client, agent)
    enabled_features = agent.enabled_features if agent and isinstance(agent.enabled_features, dict) else {}
    return {
        "tenantPublicId": settings_payload["publicWidgetId"],
        "businessName": settings_payload["businessName"],
        "agentMode": settings_payload["agentMode"],
        "widgetEnabled": settings_payload["widgetEnabled"],
        "voiceEnabled": settings_payload["voiceEnabled"],
        "primaryColor": settings_payload["widgetPrimaryColor"],
        "position": settings_payload["widgetPosition"],
        "welcomeMessage": settings_payload["widgetWelcomeMessage"],
        "features": {
            "textChat": True,
            "voice": bool(settings_payload["voiceEnabled"]),
            "siteNavigation": bool(enabled_features.get("siteNavigation", True)),
            "leadCapture": bool(enabled_features.get("leadCapture", True)),
        },
    }


async def resolve_widget_client(db: AsyncSession, public_widget_id: str) -> Client | None:
    key = (public_widget_id or "").strip()
    if not key:
        return None
    result = await db.execute(select(Client).where(Client.public_widget_key == key))
    return result.scalar_one_or_none()


async def validate_widget_request(
    db: AsyncSession,
    *,
    public_widget_id: str,
    domain: str,
) -> tuple[Client, AgentConfig | None, str, list[str], str | None]:
    client = await resolve_widget_client(db, public_widget_id)
    if not client:
        raise WidgetAccessError("WIDGET_BLOCKED", "Widget is not available for this account.")

    agent = await get_agent_config_for_client(db, client.id)
    normalized_domain = normalize_domain(domain)
    primary_domain = get_primary_domain(client, agent)
    allowed_domains = get_allowed_domains(client, agent)

    if not normalized_domain:
        raise WidgetAccessError("WIDGET_BLOCKED", "Widget is not available for this account.")
    if not is_domain_allowed(normalized_domain, allowed_domains, primary_domain):
        raise WidgetAccessError("WIDGET_BLOCKED", "Widget is not available for this account.")
    if not widget_is_enabled(client):
        raise WidgetAccessError("WIDGET_BLOCKED", "Widget is not available for this account.")
    if not client_subscription_allows_widget(client):
        raise WidgetAccessError("WIDGET_BLOCKED", "Widget is not available for this account.")

    return client, agent, normalized_domain, allowed_domains, primary_domain


def mark_widget_seen(client: Client, *, domain: str, page_url: str | None) -> None:
    client.widget_installed = True
    client.widget_last_seen_at = utcnow()
    client.widget_last_domain = normalize_domain(domain) or client.widget_last_domain
    client.widget_last_page_url = normalize_page_url(page_url) or client.widget_last_page_url


def sanitize_event_metadata(value: Any, depth: int = 0) -> Any:
    if depth > 2:
        return None
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            return value[:1000]
        return value
    if isinstance(value, list):
        items = [sanitize_event_metadata(item, depth + 1) for item in value[:20]]
        return [item for item in items if item is not None]
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in list(value.items())[:30]:
            if not isinstance(key, str):
                continue
            sanitized = sanitize_event_metadata(item, depth + 1)
            if sanitized is not None:
                clean[key[:80]] = sanitized
        return clean
    return str(value)[:1000]


async def get_or_create_widget_engagement(
    db: AsyncSession,
    *,
    client: Client,
    agent: AgentConfig | None,
    session_id: str,
    domain: str,
    page_url: str | None,
    channel: str = "website_chat",
) -> Engagement:
    result = await db.execute(
        select(Engagement).where(Engagement.client_id == client.id, Engagement.session_id == session_id)
    )
    engagement = result.scalar_one_or_none()
    normalized_page = normalize_page_url(page_url)
    if engagement:
        engagement.channel = channel
        engagement.source_url = normalized_page or engagement.source_url
        engagement.agent_mode = agent.agent_mode if agent else engagement.agent_mode
        metadata = dict(engagement.metadata or {})
        metadata["lastDomain"] = normalize_domain(domain)
        if normalized_page:
            metadata["lastPageUrl"] = normalized_page
        engagement.metadata = metadata
        return engagement

    engagement = Engagement(
        client_id=client.id,
        session_id=session_id[:120],
        channel=channel,
        source_url=normalized_page,
        lead_status="new",
        intent="other",
        contact_captured=False,
        qualified=False,
        follow_up_needed=False,
        agent_mode=agent.agent_mode if agent else "general_lead_gen",
        conversion_stage="awareness",
        metadata={
            "lastDomain": normalize_domain(domain),
            "lastPageUrl": normalized_page,
            "widgetEvents": [],
        },
    )
    db.add(engagement)
    await db.flush()
    return engagement


def append_widget_event(
    engagement: Engagement,
    *,
    event_type: str,
    domain: str,
    page_url: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    current = dict(engagement.metadata or {})
    events = current.get("widgetEvents") if isinstance(current.get("widgetEvents"), list) else []
    events.append(
        {
            "eventType": event_type,
            "domain": normalize_domain(domain),
            "pageUrl": normalize_page_url(page_url),
            "timestamp": serialize_datetime(utcnow()),
            "metadata": sanitize_event_metadata(metadata or {}),
        }
    )
    current["widgetEvents"] = events[-50:]
    current["lastDomain"] = normalize_domain(domain)
    if page_url:
        current["lastPageUrl"] = normalize_page_url(page_url)
    current["lastEventType"] = event_type
    engagement.metadata = current
    if event_type == "lead_captured":
        engagement.contact_captured = True
        engagement.lead_status = "qualified"
        engagement.conversion_stage = "lead_capture"
    elif event_type == "message_sent":
        engagement.conversion_stage = "consideration"
    elif event_type in {"voice_started", "voice_ended"}:
        engagement.channel = "ai_voice_call"


def append_widget_transcript(engagement: Engagement, speaker: str, message: str) -> None:
    line = f"{speaker}: {message.strip()}"[:4000]
    existing = (engagement.transcript or "").strip()
    engagement.transcript = f"{existing}\n{line}".strip() if existing else line
    engagement.summary_short = (message or "")[:280]
    engagement.summary_full = engagement.transcript[:8000]


def mock_chat_reply(_: str) -> str:
    return "Thanks — I can help with that. Can you tell me a little more about what you're looking for?"
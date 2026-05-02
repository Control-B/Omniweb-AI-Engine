"""Embed API — generate & validate embed authorization codes.

Embed codes are unique per client, tied to email + phone, and expire
when the subscription ends. The embed script validates the code on every
page load so it cannot be transferred or duplicated.

Endpoints:
    POST /embed/generate    — generate a new embed code (requires auth)
    POST /embed/validate    — validate an embed code (public, called by widget)
    GET  /embed/snippet     — get the embed snippet for the client (requires auth)
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Client, AgentConfig
from app.services.saas_workspace_service import client_subscription_allows_widget

logger = get_logger(__name__)
router = APIRouter(prefix="/embed", tags=["embed"])
settings = get_settings()


class GenerateEmbedRequest(BaseModel):
    phone: str
    domain: str | None = None


class ValidateEmbedRequest(BaseModel):
    embed_code: str
    domain: str | None = None


class EmbedSnippetResponse(BaseModel):
    embed_code: str
    snippet: str
    domain: str | None
    expires_at: str | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_embed_code() -> str:
    """Generate a 32-char hex embed code."""
    return secrets.token_hex(16)


@router.post("/generate")
async def generate_embed_code(
    body: GenerateEmbedRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a new embed authorization code for the authenticated client.

    The code is tied to the client's email and the phone number provided.
    It expires when the subscription ends (or never for active subscriptions).
    """
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    if not client.is_active:
        raise HTTPException(403, "Account is not active")

    # Generate new embed code
    code = _generate_embed_code()
    client.embed_code = code
    client.embed_phone = body.phone
    client.embed_domain = body.domain

    # Set expiry based on subscription status
    if client.stripe_subscription_id:
        # Active subscriber — no explicit expiry (controlled by subscription webhook)
        client.embed_expires_at = None
    elif client.trial_ends_at:
        # Trial user — expires with trial
        client.embed_expires_at = client.trial_ends_at
    else:
        # No subscription, no trial — shouldn't happen, but default 14 days
            widget_target_id = str(client.id)
            engine_url = (settings.ENGINE_BASE_URL or settings.APP_BASE_URL or "").rstrip("/")
            widget_url = f"{platform_url}/widget/{widget_target_id}"

            snippet = f"""<!-- Omniweb AI Widget -->
    <iframe
        src="{widget_url}"
        title="Omniweb AI"
        allow="microphone; autoplay"
        style="position:fixed;bottom:0;right:0;width:min(100vw - 1rem, 420px);height:min(100dvh - 1rem, 640px);max-width:420px;max-height:640px;border:0;border-radius:12px;z-index:99999;box-shadow:0 12px 48px rgba(0,0,0,0.35)"
    ></iframe>
    <!-- data-embed-code="{client.embed_code}" data-engine="{engine_url}" -->"""


@router.post("/validate")
async def validate_embed_code(
    body: ValidateEmbedRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Validate an embed code (called by the widget script on page load).

    This is a PUBLIC endpoint — no auth required. The embed code itself
    is the authorization. Returns the agent config needed to render the widget.
    """
    result = await db.execute(
        select(Client).where(Client.embed_code == body.embed_code)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(403, "Invalid embed code")

    if not client.is_active:
        raise HTTPException(403, "Account is not active")

    if not client_subscription_allows_widget(client):
        raise HTTPException(403, "Subscription or trial inactive — upgrade to continue using the widget")

    # Check expiry
    if client.embed_expires_at and client.embed_expires_at < _now():
        raise HTTPException(403, "Embed code has expired — subscription required")

    # Optional domain lock
    if client.embed_domain and body.domain:
        allowed = client.embed_domain.lower().replace("www.", "")
        provided = body.domain.lower().replace("www.", "")
        if allowed not in provided and provided not in allowed:
            logger.warning(
                f"Domain mismatch for embed {body.embed_code[:8]}: "
                f"allowed={client.embed_domain}, got={body.domain}"
            )
            raise HTTPException(403, "Embed code not authorized for this domain")

    # Get agent config for the widget
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client.id)
    )
    agent_config = result.scalar_one_or_none()

    elevenlabs_agent_id = None
    widget_config = {}
    if agent_config:
        elevenlabs_agent_id = agent_config.elevenlabs_agent_id
        widget_config = agent_config.widget_config or {}

    return {
        "valid": True,
        "client_id": str(client.id),
        "agent_id": elevenlabs_agent_id,
        "widget_config": widget_config,
        "plan": client.plan,
    }


@router.get("/snippet")
async def get_embed_snippet(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the embed snippet HTML for the authenticated client."""
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    if not client.embed_code:
        raise HTTPException(404, "No embed code generated yet. Generate one first.")

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client.id)
    )
    agent_config = result.scalar_one_or_none()
    agent_id = agent_config.elevenlabs_agent_id if agent_config else "YOUR_AGENT_ID"

    platform_url = settings.PLATFORM_URL.rstrip("/")
    widget_target_id = str(client.id)
    widget_url = f"{platform_url}/widget/{widget_target_id}"
    engine_url = (settings.ENGINE_BASE_URL or settings.APP_BASE_URL or "").rstrip("/")

    snippet = f"""<!-- Omniweb AI Widget -->
<iframe
  src="{widget_url}"
  title="Omniweb AI"
  allow="microphone; autoplay"
  style="position:fixed;bottom:0;right:0;width:min(100vw - 1rem, 420px);height:min(100dvh - 1rem, 640px);max-width:420px;max-height:640px;border:0;border-radius:12px;z-index:99999;box-shadow:0 12px 48px rgba(0,0,0,0.35)"
></iframe>
<!-- data-embed-code="{client.embed_code}" data-agent-id="{agent_id}" data-engine="{engine_url}" -->"""

    return {
        "embed_code": client.embed_code,
        "snippet": snippet,
        "domain": client.embed_domain,
        "expires_at": client.embed_expires_at.isoformat() if client.embed_expires_at else None,
    }


@router.get("/verify-domain/{embed_code}")
async def get_domain_verification(
    embed_code: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get domain verification instructions for an embed code.

    Returns a meta tag the client should add to their website's <head>
    to prove domain ownership. Once verified, the embed is domain-locked.
    """
    result = await db.execute(
        select(Client).where(Client.embed_code == embed_code)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Invalid embed code")

    verification_token = f"omniweb-verify-{embed_code[:16]}"

    return {
        "verification_token": verification_token,
        "meta_tag": f'<meta name="omniweb-site-verification" content="{verification_token}" />',
        "instructions": (
            "Add this meta tag to the <head> of your website's homepage, "
            "then call POST /api/embed/verify-domain to complete verification."
        ),
        "current_domain": client.embed_domain,
    }


class VerifyDomainRequest(BaseModel):
    embed_code: str
    domain: str


@router.post("/verify-domain")
async def verify_domain_ownership(
    body: VerifyDomainRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Verify domain ownership by checking for the meta tag on the client's site.

    This locks the embed code to the verified domain for security.
    """
    import httpx as _httpx

    client = await db.get(Client, current_client["client_id"])
    if not client or client.embed_code != body.embed_code:
        raise HTTPException(403, "Invalid embed code")

    verification_token = f"omniweb-verify-{body.embed_code[:16]}"
    domain = body.domain.strip().lower().replace("www.", "")

    # Check for the verification meta tag on the domain
    try:
        async with _httpx.AsyncClient(timeout=10, follow_redirects=True) as http:
            resp = await http.get(f"https://{domain}")
            if verification_token not in resp.text:
                # Try www variant
                resp = await http.get(f"https://www.{domain}")
                if verification_token not in resp.text:
                    raise HTTPException(
                        400,
                        f"Verification meta tag not found on {domain}. "
                        "Please add it to your site's <head> and try again.",
                    )
    except _httpx.HTTPError as e:
        raise HTTPException(400, f"Could not reach {domain}: {str(e)}")

    # Domain verified — lock embed to this domain
    client.embed_domain = domain
    await db.commit()

    logger.info(f"Domain {domain} verified for client {client.email}")

    return {
        "verified": True,
        "domain": domain,
        "message": f"Domain {domain} has been verified and locked to your embed code.",
    }

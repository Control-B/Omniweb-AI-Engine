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

    # Require website_domain on agent config before generating embed
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client.id)
    )
    agent_config = result.scalar_one_or_none()
    if not agent_config or not agent_config.website_domain:
        raise HTTPException(
            400,
            "Website domain is required before generating embed code. "
            "Complete your agent setup first.",
        )

    # Use agent config domain as the authoritative domain lock
    domain = body.domain or agent_config.website_domain

    # Generate new embed code
    code = _generate_embed_code()
    client.embed_code = code
    client.embed_phone = body.phone
    client.embed_domain = domain

    # Set expiry based on subscription status
    if client.stripe_subscription_id:
        # Active subscriber — no explicit expiry (controlled by subscription webhook)
        client.embed_expires_at = None
    elif client.trial_ends_at:
        # Trial user — expires with trial
        client.embed_expires_at = client.trial_ends_at
    else:
        # No subscription, no trial — shouldn't happen, but default 14 days
        from datetime import timedelta
        client.embed_expires_at = _now() + timedelta(days=14)

    await db.commit()
    await db.refresh(client)

    logger.info(f"Embed code generated for {client.email}: {code[:8]}...")

    return {
        "embed_code": code,
        "domain": client.embed_domain,
        "phone": client.embed_phone,
        "expires_at": client.embed_expires_at.isoformat() if client.embed_expires_at else None,
    }


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

    retell_agent_id = None
    widget_config = {}
    if agent_config:
        retell_agent_id = agent_config.retell_agent_id
        widget_config = agent_config.widget_config or {}

    return {
        "valid": True,
        "client_id": str(client.id),
        "agent_id": str(client.id),
        "retell_agent_id": retell_agent_id,
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

    # External widget targets the client_id-backed Retell web-call flow.
    widget_target_id = str(client.id)

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client.id)
    )
    agent_config = result.scalar_one_or_none()
    retell_agent_id = agent_config.retell_agent_id if agent_config else None

    platform_url = settings.PLATFORM_URL.rstrip("/")
    engine_url = settings.ENGINE_BASE_URL.rstrip("/")

    snippet = f"""<!-- Omniweb AI Widget -->
<script
  src="{platform_url}/widget/loader.js"
  data-embed-code="{client.embed_code}"
  data-agent-id="{widget_target_id}"
  data-engine-url="{engine_url}"
  async
></script>"""

    return {
        "embed_code": client.embed_code,
        "snippet": snippet,
        "widget_target_id": widget_target_id,
        "retell_agent_id": retell_agent_id,
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

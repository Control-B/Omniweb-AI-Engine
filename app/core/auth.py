"""Authentication & authorization for the Omniweb Agent Engine.

Four auth strategies:

1. **Dashboard JWT** — issued on login, validated on every dashboard API request.
   The JWT payload contains `{"sub": client_id, "email": email, "plan": plan}`.
   Issued by POST /auth/login (email + password verified against the Client
   table's hashed password).

2. **Clerk JWT** — issued by Clerk after social/email login. Validated using
   Clerk's JWKS public keys. On first login a Client record is auto-created
   (or linked via email).

3. **API Key** — per-client API key stored in the Client table, used for
   external integrations (CRM, Zapier, Make, etc.).
   Passed as `Authorization: Bearer omniweb_key_...` or `X-API-Key: ...`.

4. **Internal Key** — shared secret between FastAPI and the agent worker.
   Passed as `X-Internal-Key: ...` header.

Webhooks (ElevenLabs, Stripe) have their own signature verification — no JWT.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt as pyjwt
from jwt import PyJWKClient
from fastapi import Depends, Header, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_bearer_scheme = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
INTERNAL_STAFF_ROLES = {"owner", "admin", "support"}
OWNER_WILDCARD_PERMISSION = "*"
RBAC_PERMISSIONS = {
    "overview.read",
    "clients.read",
    "clients.write",
    "clients.impersonate",
    "agents.read",
    "conversations.read",
    "templates.read",
    "templates.write",
    "team.read",
    "team.manage",
}
DEFAULT_ROLE_PERMISSIONS = {
    "owner": [OWNER_WILDCARD_PERMISSION],
    "admin": [
        "overview.read",
        "clients.read",
        "clients.write",
        "agents.read",
        "conversations.read",
        "templates.read",
        "templates.write",
    ],
    "support": [
        "overview.read",
        "clients.read",
        "agents.read",
        "conversations.read",
        "templates.read",
    ],
    "client": [],
}

# ── Clerk JWKS Client (cached, thread-safe) ──────────────────────────────────
_clerk_jwks_client: Optional[PyJWKClient] = None


def is_internal_staff_role(role: Optional[str]) -> bool:
    return (role or "") in INTERNAL_STAFF_ROLES


def normalize_permissions(permissions: Optional[list[str]]) -> list[str]:
    if not permissions:
        return []
    normalized: list[str] = []
    for permission in permissions:
        if not permission:
            continue
        if permission == OWNER_WILDCARD_PERMISSION or permission in RBAC_PERMISSIONS:
            if permission not in normalized:
                normalized.append(permission)
    return normalized


def get_default_permissions_for_role(role: Optional[str]) -> list[str]:
    return list(DEFAULT_ROLE_PERMISSIONS.get(role or "client", []))


def get_effective_permissions(role: Optional[str], permissions: Optional[list[str]] = None) -> list[str]:
    if role == "owner":
        return [OWNER_WILDCARD_PERMISSION]
    explicit = normalize_permissions(permissions)
    if explicit:
        return explicit
    return get_default_permissions_for_role(role)


def has_permission(client: dict, permission: str) -> bool:
    permissions = client.get("permissions") or []
    return OWNER_WILDCARD_PERMISSION in permissions or permission in permissions


def _get_clerk_jwks_client() -> Optional[PyJWKClient]:
    """Lazily initialise the JWKS client for Clerk token verification."""
    global _clerk_jwks_client
    if _clerk_jwks_client is not None:
        return _clerk_jwks_client
    if not settings.clerk_configured:
        return None

    # Clerk JWKS URL: either explicit or derived from the publishable key
    jwks_url = settings.CLERK_JWKS_URL
    if not jwks_url:
        # Clerk publishable keys look like pk_test_abc... or pk_live_abc...
        # The JWKS endpoint is always at https://<frontend-api>/.well-known/jwks.json
        # We can derive it from the secret key's instance or use a known pattern
        jwks_url = "https://api.clerk.com/.well-known/jwks.json"
        # Try to derive from CLERK_PUBLISHABLE_KEY (pk_test_<base64-encoded-frontend-api>)
        pk = settings.CLERK_PUBLISHABLE_KEY
        if pk:
            import base64
            try:
                # pk format: pk_test_<base64url(frontend-api-url)> or pk_live_<base64url(...)>
                parts = pk.split("_", 2)
                if len(parts) == 3:
                    encoded = parts[2]
                    # Add padding if needed
                    padding = 4 - len(encoded) % 4
                    if padding != 4:
                        encoded += "=" * padding
                    frontend_api = base64.b64decode(encoded).decode().rstrip("$")
                    jwks_url = f"https://{frontend_api}/.well-known/jwks.json"
            except Exception:
                pass  # Fall back to default

    _clerk_jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    logger.info(f"Clerk JWKS client initialised: {jwks_url}")
    return _clerk_jwks_client


# ── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password with salt using PBKDF2-SHA256."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt, expected = hashed.split("$", 1)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(h.hex(), expected)
    except (ValueError, AttributeError):
        return False


# ── API Key Generation ────────────────────────────────────────────────────────

def generate_api_key() -> str:
    """Generate a prefixed API key: omniweb_key_<random>."""
    return f"omniweb_key_{secrets.token_hex(24)}"


def hash_api_key(key: str) -> str:
    """One-way hash for storing API keys in the DB."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_secure_token() -> str:
    """Generate a URL-safe token for password reset and invite flows."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """One-way hash for storing reset/invite tokens in the DB."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── JWT Tokens ────────────────────────────────────────────────────────────────

def create_access_token(
    client_id: str,
    email: str,
    plan: str = "starter",
    role: str = "client",
    permissions: Optional[list[str]] = None,
    extra: Optional[dict] = None,
) -> str:
    """Create a JWT access token for dashboard login."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": client_id,
        "email": email,
        "plan": plan,
        "role": role,
        "permissions": get_effective_permissions(role, permissions),
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token. Raises on invalid/expired."""
    return pyjwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

async def get_current_client(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    x_api_key: Optional[str] = Header(None),
) -> dict:
    """Extract the authenticated client from JWT, Clerk token, or API key.

    Returns {"client_id": str, "email": str, "plan": str, "auth_method": str}.
    Raises 401 if no valid credentials.
    """
    # Try JWT first
    if credentials and credentials.credentials:
        token = credentials.credentials
        # Check if it's an API key (starts with omniweb_key_)
        if token.startswith("omniweb_key_"):
            return await _resolve_api_key(token)

        # Try our own JWT first
        try:
            payload = decode_access_token(token)
            return {
                "client_id": payload["sub"],
                "email": payload.get("email", ""),
                "plan": payload.get("plan", "starter"),
                "role": payload.get("role", "client"),
                  "permissions": get_effective_permissions(payload.get("role", "client"), payload.get("permissions")),
                "auth_method": "jwt",
            }
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
            pass  # Fall through to try Clerk

        # Try Clerk JWT if configured
        if settings.clerk_configured:
            try:
                return await _resolve_clerk_token(token)
            except HTTPException:
                raise
            except Exception as e:
                logger.debug(f"Clerk token verification failed: {e}")
                pass

        # Neither worked — raise appropriate error
        raise HTTPException(401, "Invalid or expired token")

    # Try X-API-Key header
    if x_api_key:
        return await _resolve_api_key(x_api_key)

    raise HTTPException(401, "Authentication required")


async def _resolve_api_key(key: str) -> dict:
    """Look up a client by API key hash."""
    from app.core.database import AsyncSessionLocal
    from app.models.models import Client

    key_hash = hash_api_key(key)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Client).where(Client.api_key_hash == key_hash, Client.is_active == True)
        )
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(401, "Invalid API key")
        return {
            "client_id": str(client.id),
            "email": client.email,
            "plan": client.plan,
            "role": client.role,
              "permissions": get_effective_permissions(client.role, getattr(client, "permissions", None)),
            "auth_method": "api_key",
        }


async def _resolve_clerk_token(token: str) -> dict:
    """Verify a Clerk-issued JWT and resolve (or create) the matching Client.

    Clerk JWTs are signed with RS256 and verified against Clerk's JWKS endpoint.
    The `sub` claim is the Clerk user ID (e.g. `user_2abc...`).
    We look up the Client by `clerk_user_id`; if not found, we look up by email
    and link the account; if still not found, we auto-provision a new Client.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import AgentConfig, Client

    jwks_client = _get_clerk_jwks_client()
    if not jwks_client:
        raise HTTPException(401, "Clerk auth not configured")

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk doesn't always set aud
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Clerk token expired")
    except Exception as e:
        logger.warning(f"Clerk JWT verification error: {e}")
        raise HTTPException(401, "Invalid Clerk token")

    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(401, "Invalid Clerk token: missing sub")

    # Extract email from Clerk JWT claims
    # Clerk puts email in different places depending on config
    email = (
        payload.get("email")
        or payload.get("primary_email_address")
        or (payload.get("email_addresses", [{}])[0].get("email_address") if payload.get("email_addresses") else None)
        or ""
    )
    full_name = (
        payload.get("name")
        or f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip()
        or email.split("@")[0] if email else "User"
    )

    async with AsyncSessionLocal() as db:
        # 1. Try by clerk_user_id
        result = await db.execute(
            select(Client).where(Client.clerk_user_id == clerk_user_id, Client.is_active == True)
        )
        client = result.scalar_one_or_none()

        if not client and email:
            # 2. Try by email (link existing account)
            result = await db.execute(
                select(Client).where(Client.email == email, Client.is_active == True)
            )
            client = result.scalar_one_or_none()
            if client:
                client.clerk_user_id = clerk_user_id
                await db.commit()
                logger.info(f"Linked Clerk user {clerk_user_id} to existing client {client.id}")

        if not client:
            # 3. Auto-provision Clerk-only tenant. Trial starts on SaaS onboarding (7 days).
            import uuid as _uuid

            client = Client(
                id=_uuid.uuid4(),
                name=full_name,
                email=email,
                hashed_password="",  # No password — Clerk-only auth
                clerk_user_id=clerk_user_id,
                role="client",
                plan="starter",
                is_active=True,
            )
            db.add(client)
            await db.flush()

            agent_config = AgentConfig(
                client_id=client.id,
                agent_name="AI Assistant",
                agent_greeting="Hello! How can I help you today?",
                system_prompt="You are a helpful AI assistant.",
                llm_model="gpt-4o",
                business_name=full_name,
            )
            db.add(agent_config)

            await db.commit()
            await db.refresh(client)
            logger.info(f"Auto-provisioned client {client.id} from Clerk user {clerk_user_id}")

            # Fire welcome email (non-blocking)
            try:
                import asyncio
                from app.services.email_service import send_welcome_email
                asyncio.create_task(send_welcome_email(to=email, name=full_name))
            except Exception:
                pass  # Non-critical

        return {
            "client_id": str(client.id),
            "email": client.email,
            "plan": client.plan,
            "role": client.role,
              "permissions": get_effective_permissions(client.role, getattr(client, "permissions", None)),
            "auth_method": "clerk",
        }


def verify_internal_key(x_internal_key: str = Header(...)) -> None:
    """Verify the internal shared secret (agent worker ↔ FastAPI)."""
    if not hmac.compare_digest(x_internal_key, settings.INTERNAL_API_KEY):
        raise HTTPException(403, "Invalid internal key")


def require_plan(*allowed_plans: str):
    """Dependency that checks the client's plan tier."""
    async def _check(client: dict = Depends(get_current_client)):
        if client["plan"] not in allowed_plans:
            raise HTTPException(
                403,
                f"This feature requires one of: {', '.join(allowed_plans)}. "
                f"Your plan: {client['plan']}",
            )
        return client
    return _check


async def require_admin(
    client: dict = Depends(get_current_client),
) -> dict:
    """Dependency that restricts access to internal staff users."""
    if not is_internal_staff_role(client.get("role")):
        raise HTTPException(403, "Internal staff access required")
    client["permissions"] = get_effective_permissions(client.get("role"), client.get("permissions"))
    return client


async def require_owner(
    client: dict = Depends(get_current_client),
) -> dict:
    """Dependency that restricts access to the workspace owner."""
    if client.get("role") != "owner":
        raise HTTPException(403, "Owner access required")
    return client


def require_owner_or_admin(client_id_param: str = "client_id"):
    """Dependency factory: allows access only if the authenticated user
    owns the resource (client_id matches) OR is an admin."""
    async def _check(
        client: dict = Depends(get_current_client),
        **kwargs,
    ):
        return client
    return _check


def require_permissions(*required_permissions: str):
    async def _check(client: dict = Depends(require_admin)) -> dict:
        missing = [permission for permission in required_permissions if not has_permission(client, permission)]
        if missing:
            raise HTTPException(403, f"Missing required permissions: {', '.join(missing)}")
        return client

    return _check


# ── Plan Limits & Trial Enforcement ──────────────────────────────────────────

PLAN_MINUTE_LIMITS = {
    "starter": 500,
    "growth": 2500,
    "pro": 999_999,       # effectively unlimited
    "agency": 999_999,
}


async def require_active_subscription(
    client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(lambda: None),  # overridden by route
) -> dict:
    """Dependency that blocks requests when trial expired and no active subscription.

    Admins are always allowed. Usage within limits is allowed during trial.
    """
    if is_internal_staff_role(client.get("role")):
        return client

    from app.core.database import AsyncSessionLocal
    from app.models.models import Client as ClientModel

    async with AsyncSessionLocal() as session:
        c = await session.get(ClientModel, client["client_id"])
        if not c:
            raise HTTPException(404, "Client not found")

        now = datetime.now(timezone.utc)

        # Has active Stripe subscription → allowed
        if c.stripe_subscription_id:
            # Check usage limits
            limit = PLAN_MINUTE_LIMITS.get(c.plan, 500)
            if c.plan_minutes_used >= limit:
                raise HTTPException(
                    402,
                    f"You have used all {limit} minutes in your {c.plan} plan. "
                    "Please upgrade your plan.",
                )
            return client

        # In trial period → allowed (with limits)
        if c.trial_ends_at and c.trial_ends_at > now:
            limit = PLAN_MINUTE_LIMITS.get("starter", 500)
            if c.plan_minutes_used >= limit:
                raise HTTPException(
                    402,
                    f"You have used all {limit} trial minutes. "
                    "Please subscribe to continue.",
                )
            return client

        # Trial expired, no subscription → blocked
        if c.trial_ends_at and c.trial_ends_at <= now:
            raise HTTPException(
                402,
                "Your free trial has expired. Please subscribe to continue using Omniweb.",
            )

        # No trial set (legacy user) → allowed
        return client

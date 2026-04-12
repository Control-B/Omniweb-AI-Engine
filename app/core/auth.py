"""Authentication & authorization for the Omniweb Agent Engine.

Three auth strategies:

1. **Dashboard JWT** — issued on login, validated on every dashboard API request.
   The JWT payload contains `{"sub": client_id, "email": email, "plan": plan}`.
   Issued by POST /auth/login (email + password verified against Supabase or
   the Client table's hashed password).

2. **API Key** — per-client API key stored in the Client table, used for
   external integrations (CRM, Zapier, Make, etc.).
   Passed as `Authorization: Bearer omniweb_key_...` or `X-API-Key: ...`.

3. **Internal Key** — shared secret between FastAPI and the agent worker.
   Passed as `X-Internal-Key: ...` header.

Webhooks (ElevenLabs, Stripe) have their own signature verification — no JWT.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as pyjwt
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
    extra: Optional[dict] = None,
) -> str:
    """Create a JWT access token for dashboard login."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": client_id,
        "email": email,
        "plan": plan,
        "role": role,
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
    """Extract the authenticated client from JWT or API key.

    Returns {"client_id": str, "email": str, "plan": str, "auth_method": str}.
    Raises 401 if no valid credentials.
    """
    # Try JWT first
    if credentials and credentials.credentials:
        token = credentials.credentials
        # Check if it's an API key (starts with omniweb_key_)
        if token.startswith("omniweb_key_"):
            return await _resolve_api_key(token)
        # Otherwise treat as JWT
        try:
            payload = decode_access_token(token)
            return {
                "client_id": payload["sub"],
                "email": payload.get("email", ""),
                "plan": payload.get("plan", "starter"),
                "role": payload.get("role", "client"),
                "auth_method": "jwt",
            }
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except pyjwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")

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
            "auth_method": "api_key",
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
    """Dependency that restricts access to admin users only."""
    if client.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
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

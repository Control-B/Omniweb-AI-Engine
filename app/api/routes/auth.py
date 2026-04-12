"""Auth API — login, signup, token refresh, API key management.

Endpoints:
    POST /auth/signup    — create a new client + agent config
    POST /auth/login     — email + password → JWT
    GET  /auth/admin/users   — list admin/team users
    POST /auth/admin/users   — create an admin/team user
    POST /auth/refresh   — extend JWT lifetime
    POST /auth/api-key   — generate a new API key for the client
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import (
    create_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
    decode_access_token,
    get_current_client,
    require_admin,
)
from app.core.logging import get_logger
from app.models.models import AgentConfig, AgentTemplate, Client

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    template_id: Optional[str] = None  # UUID of template to apply


class LoginRequest(BaseModel):
    email: str
    password: str
    portal: Literal["client", "admin"] = "client"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    client_id: str
    email: str
    plan: str
    role: str = "client"


class ApiKeyResponse(BaseModel):
    api_key: str
    note: str = "Save this key — it cannot be retrieved again."


class ProfileResponse(BaseModel):
    client_id: str
    name: str
    email: str
    plan: str
    role: str
    crm_webhook_url: str | None = None
    notification_email: str | None = None
    business_name: str | None = None
    business_type: str | None = None
    created_at: str | None = None


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    notification_email: str | None = None
    crm_webhook_url: str | None = None
    business_name: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminUserCreateRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class AdminUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: str | None = None


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new client account and return a JWT."""
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    # Check if email already exists
    result = await db.execute(
        select(Client).where(Client.email == body.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")

    # Create client
    client = Client(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        plan="starter",
        role="client",
        is_active=True,
    )
    db.add(client)
    await db.flush()

    # Resolve template: explicit template_id → default template → built-in defaults
    template = None
    if body.template_id:
        template = await db.get(AgentTemplate, body.template_id)
    if not template:
        result_tpl = await db.execute(
            select(AgentTemplate).where(
                AgentTemplate.is_default == True,
                AgentTemplate.is_active == True,
            ).limit(1)
        )
        template = result_tpl.scalar_one_or_none()

    # Create agent config from template (or defaults)
    agent_config = AgentConfig(
        client_id=client.id,
        agent_name=template.agent_name if template else "AI Assistant",
        agent_greeting=template.agent_greeting if template else "Hello! How can I help you today?",
        system_prompt=template.system_prompt if template else "You are a helpful AI assistant.",
        voice_id=template.voice_id if template else "EXAVITQu4vr4xnSDxMaL",
        voice_stability=template.voice_stability if template else 0.5,
        voice_similarity_boost=template.voice_similarity_boost if template else 0.75,
        llm_model=template.llm_model if template else "gpt-4o",
        temperature=template.temperature if template else 0.7,
        max_call_duration=template.max_call_duration if template else 1800,
        after_hours_message=template.after_hours_message if template else "We're currently closed but will call you back first thing in the morning.",
        after_hours_sms_enabled=template.after_hours_sms_enabled if template else True,
        allow_interruptions=template.allow_interruptions if template else True,
        services=template.services if template else [],
        business_hours=template.business_hours if template else {},
        widget_config=template.widget_config if template else {},
        business_name=body.business_name or body.name,
        business_type=body.business_type or (template.industry if template else None),
    )
    db.add(agent_config)
    await db.commit()
    await db.refresh(client)

    # Issue JWT
    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
    )

    logger.info(f"New client signup: {client.email} ({client.id})")

    # Fire welcome email (non-blocking)
    import asyncio
    from app.services.email_service import send_welcome_email
    asyncio.create_task(send_welcome_email(to=client.email, name=client.name))

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Authenticate with email + password and receive a JWT."""
    result = await db.execute(
        select(Client).where(Client.email == body.email, Client.is_active == True)
    )
    client = result.scalar_one_or_none()

    if not client or not client.hashed_password:
        raise HTTPException(401, "Invalid email or password")

    if not verify_password(body.password, client.hashed_password):
        raise HTTPException(401, "Invalid email or password")

    if body.portal == "admin" and client.role != "admin":
        raise HTTPException(401, "Invalid email or password")

    if body.portal == "client" and client.role == "admin":
        raise HTTPException(401, "Use the admin sign-in portal for this account")

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
    )

    logger.info(f"{body.portal.title()} login: {client.email}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
    }


@router.get("/admin/users", response_model=list[AdminUserResponse])
async def list_admin_users(
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List all admin/team users stored in the DB."""
    result = await db.execute(
        select(Client)
        .where(Client.role == "admin")
        .order_by(Client.created_at.asc())
    )
    users = result.scalars().all()
    return [
        {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for user in users
    ]


@router.post("/admin/users", response_model=AdminUserResponse, status_code=201)
async def create_admin_user(
    body: AdminUserCreateRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a DB-backed admin/team login with email + password."""
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    existing = await db.execute(select(Client).where(Client.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")

    user = Client(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role="admin",
        plan="pro",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin team user created by {admin['email']}: {user.email}")

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/demo-token", response_model=TokenResponse)
async def demo_token(
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a JWT for the demo account (no password required).

    Auto-creates the demo client if it doesn't exist yet.
    Used by the /demo page to provide one-click access.
    """
    demo_email = "demo@omniweb.ai"
    demo_password = "demo1234"

    result = await db.execute(
        select(Client).where(Client.email == demo_email)
    )
    client = result.scalar_one_or_none()

    if not client:
        # Auto-create the demo account
        client = Client(
            name="Demo User",
            email=demo_email,
            hashed_password=hash_password(demo_password),
            plan="pro",
            role="client",
            is_active=True,
        )
        db.add(client)
        await db.flush()

        # Create a demo agent config
        agent_config = AgentConfig(
            client_id=client.id,
            agent_name="Demo AI Assistant",
            agent_greeting="Hello! This is a demo of the Omniweb AI phone agent.",
            system_prompt="You are a helpful AI assistant for a demo business.",
            voice_id="EXAVITQu4vr4xnSDxMaL",
            business_name="Demo Business",
            business_type="demo",
        )
        db.add(agent_config)
        await db.commit()
        await db.refresh(client)
        logger.info(f"Auto-created demo account: {demo_email}")

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
    )

    logger.info(f"Demo token issued for {client.email}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Refresh the JWT for the current authenticated client."""
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(401, "Client not found")

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
    }


@router.post("/api-key", response_model=ApiKeyResponse)
async def create_api_key(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a new API key for the authenticated client.

    The raw key is returned only once — store it securely.
    """
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    raw_key = generate_api_key()
    client.api_key_hash = hash_api_key(raw_key)
    await db.commit()

    logger.info(f"API key generated for {client.email}")

    return {
        "api_key": raw_key,
        "note": "Save this key — it cannot be retrieved again.",
    }


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return the authenticated client's profile."""
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    # Get business name from agent config
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client.id)
    )
    agent_config = result.scalar_one_or_none()

    return {
        "client_id": str(client.id),
        "name": client.name,
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
        "crm_webhook_url": client.crm_webhook_url,
        "notification_email": client.notification_email,
        "business_name": agent_config.business_name if agent_config else None,
        "business_type": agent_config.business_type if agent_config else None,
        "created_at": client.created_at.isoformat() if client.created_at else None,
    }


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Update the authenticated client's profile fields."""
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    if body.name is not None:
        client.name = body.name
    if body.notification_email is not None:
        client.notification_email = body.notification_email
    if body.crm_webhook_url is not None:
        client.crm_webhook_url = body.crm_webhook_url

    # Update business_name on agent config too
    if body.business_name is not None:
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.client_id == client.id)
        )
        agent_config = result.scalar_one_or_none()
        if agent_config:
            agent_config.business_name = body.business_name

    await db.commit()
    await db.refresh(client)

    # Re-fetch agent config for response
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client.id)
    )
    agent_config = result.scalar_one_or_none()

    logger.info(f"Profile updated for {client.email}")

    return {
        "client_id": str(client.id),
        "name": client.name,
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
        "crm_webhook_url": client.crm_webhook_url,
        "notification_email": client.notification_email,
        "business_name": agent_config.business_name if agent_config else None,
        "business_type": agent_config.business_type if agent_config else None,
        "created_at": client.created_at.isoformat() if client.created_at else None,
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Change password for the authenticated client."""
    if len(body.new_password) < 6:
        raise HTTPException(400, "New password must be at least 6 characters")

    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Client not found")

    if not client.hashed_password or not verify_password(body.current_password, client.hashed_password):
        raise HTTPException(401, "Current password is incorrect")

    client.hashed_password = hash_password(body.new_password)
    await db.commit()

    logger.info(f"Password changed for {client.email}")

    return {"ok": True, "message": "Password changed successfully"}

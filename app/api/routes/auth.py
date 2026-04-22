"""Auth API — login, signup, token refresh, API key management.

Endpoints:
    POST /auth/signup    — create a new client + agent config
    POST /auth/login     — email + password → JWT
    POST /auth/forgot-password — issue a password reset email
    POST /auth/reset-password  — set a new password from reset token
    POST /auth/accept-invite   — accept a team invite and set password
    GET  /auth/admin/users   — list admin/team users
    POST /auth/admin/users   — create an admin/team user
    POST /auth/admin/users/invite — invite an admin/team user by email
    POST /auth/refresh   — extend JWT lifetime
    POST /auth/api-key   — generate a new API key for the client
"""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import (
    create_access_token,
    get_default_permissions_for_role,
    get_effective_permissions,
    generate_api_key,
    hash_api_key,
    hash_password,
    hash_token,
    normalize_permissions,
    verify_password,
    decode_access_token,
    generate_secure_token,
    get_current_client,
    require_admin,
    require_owner,
    require_permissions,
    is_internal_staff_role,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, AgentTemplate, Client

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
INTERNAL_TEAM_ROLES = ("owner", "admin", "support")


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    website_domain: Optional[str] = None
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
    permissions: list[str] = []


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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    portal: Literal["client", "admin"] = "client"


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    name: str | None = None


class AdminUserCreateRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["admin", "support"] = "admin"
    permissions: list[str] | None = None


class AdminUserInviteRequest(BaseModel):
    name: str
    email: EmailStr
    role: Literal["admin", "support"] = "admin"
    permissions: list[str] | None = None


class AdminUserStatusRequest(BaseModel):
    is_active: bool


class AdminUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    permissions: list[str]
    is_active: bool
    created_at: str | None = None
    invited_at: str | None = None
    invite_accepted_at: str | None = None
    invite_url: str | None = None
    invite_code: str | None = None
    reset_url: str | None = None
    reset_code: str | None = None


class AdminBootstrapStatusResponse(BaseModel):
    bootstrap_open: bool
    has_owner: bool
    internal_user_count: int


class AdminUserUpdateRequest(BaseModel):
    role: Literal["admin", "support"] | None = None
    permissions: list[str] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reset_url(token: str) -> str:
    return f"{settings.PLATFORM_URL}/reset-password?token={token}&mode=reset"


def _invite_url(token: str) -> str:
    return f"{settings.PLATFORM_URL}/reset-password?token={token}&mode=invite"


def _serialize_admin_user(
    user: Client,
    *,
    invite_url: str | None = None,
    invite_code: str | None = None,
    reset_url: str | None = None,
    reset_code: str | None = None,
) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "permissions": get_effective_permissions(user.role, user.permissions),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "invited_at": user.invited_at.isoformat() if user.invited_at else None,
        "invite_accepted_at": user.invite_accepted_at.isoformat() if user.invite_accepted_at else None,
        "invite_url": invite_url,
        "invite_code": invite_code,
        "reset_url": reset_url,
        "reset_code": reset_code,
    }


async def _has_owner(db: AsyncSession) -> bool:
    result = await db.execute(
        select(Client.id).where(Client.role == "owner").limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _count_internal_users(db: AsyncSession) -> int:
    result = await db.execute(
        select(Client.id).where(Client.role.in_(INTERNAL_TEAM_ROLES))
    )
    return len(result.scalars().all())


async def _ensure_owner_role(user: Client, db: AsyncSession) -> Client:
    if user.role != "admin":
        return user
    if await _has_owner(db):
        return user

    user.role = "owner"
    await db.commit()
    await db.refresh(user)
    logger.info(f"Promoted bootstrap internal user to owner: {user.email}")
    return user


async def _issue_password_reset(*, user: Client, db: AsyncSession) -> str:
    token = generate_secure_token()
    user.password_reset_token_hash = hash_token(token)
    user.password_reset_expires_at = _now() + timedelta(hours=1)
    await db.commit()
    return token


async def _issue_invite(*, user: Client, db: AsyncSession) -> str:
    token = generate_secure_token()
    user.invite_token_hash = hash_token(token)
    user.invite_expires_at = _now() + timedelta(hours=72)
    user.invited_at = _now()
    await db.commit()
    return token


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

    # Normalize and validate domain
    domain = None
    if body.website_domain:
        domain = body.website_domain.strip().lower()
        # Strip protocol and trailing slashes
        for prefix in ("https://", "http://", "www."):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        domain = domain.rstrip("/")
        if not domain or "." not in domain:
            raise HTTPException(400, "Please enter a valid domain (e.g. mybusiness.com)")
        # Check domain uniqueness
        existing_domain = await db.execute(
            select(AgentConfig).where(AgentConfig.website_domain == domain)
        )
        if existing_domain.scalar_one_or_none():
            raise HTTPException(409, "An agent already exists for this domain")

    # Create client
    from datetime import timedelta
    client = Client(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        plan="starter",
        role="client",
        is_active=True,
        trial_ends_at=_now() + timedelta(days=14),
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
        website_domain=domain,
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
          permissions=get_effective_permissions(client.role, client.permissions),
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

    client = await _ensure_owner_role(client, db)

    if body.portal == "admin" and not is_internal_staff_role(client.role):
        raise HTTPException(401, "Invalid email or password")

    if body.portal == "client" and is_internal_staff_role(client.role):
        raise HTTPException(401, "Use the admin sign-in portal for this account")

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
          permissions=get_effective_permissions(client.role, client.permissions),
    )

    logger.info(f"{body.portal.title()} login: {client.email}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
          "permissions": get_effective_permissions(client.role, client.permissions),
    }


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Issue a password reset email without revealing whether the account exists."""
    result = await db.execute(
        select(Client).where(Client.email == body.email, Client.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user:
        portal_matches = (body.portal == "admin" and is_internal_staff_role(user.role)) or (
            body.portal == "client" and not is_internal_staff_role(user.role)
        )
        if portal_matches:
            token = await _issue_password_reset(user=user, db=db)
            import asyncio
            from app.services.email_service import send_password_reset_email

            asyncio.create_task(
                send_password_reset_email(
                    to=user.email,
                    name=user.name,
                    reset_url=_reset_url(token),
                )
            )
            logger.info(f"Password reset requested for {user.email}")

    return {"ok": True, "message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Set a new password using a valid reset token."""
    if len(body.new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    result = await db.execute(
        select(Client).where(Client.password_reset_token_hash == hash_token(body.token))
    )
    user = result.scalar_one_or_none()
    if not user or not user.password_reset_expires_at or user.password_reset_expires_at < _now():
        raise HTTPException(400, "Reset link is invalid or expired")

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    await db.commit()

    logger.info(f"Password reset completed for {user.email}")
    return {"ok": True, "message": "Password reset successfully"}


@router.post("/accept-invite")
async def accept_invite(
    body: AcceptInviteRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Accept a DB-backed admin invite and set the initial password."""
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    result = await db.execute(
        select(Client).where(
            Client.invite_token_hash == hash_token(body.token),
            Client.role.in_(INTERNAL_TEAM_ROLES),
        )
    )
    user = result.scalar_one_or_none()
    if not user or not user.invite_expires_at or user.invite_expires_at < _now():
        raise HTTPException(400, "Invite is invalid or expired")

    if body.name:
        user.name = body.name
    user.hashed_password = hash_password(body.password)
    user.invite_token_hash = None
    user.invite_expires_at = None
    user.invite_accepted_at = _now()
    user.is_active = True
    await db.commit()

    logger.info(f"Invite accepted for internal user {user.email}")
    return {"ok": True, "message": "Invite accepted successfully"}


@router.get("/admin/users", response_model=list[AdminUserResponse])
async def list_admin_users(
    admin: dict = Depends(require_permissions("team.read")),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List all internal team users stored in the DB."""
    result = await db.execute(
        select(Client)
        .where(Client.role.in_(INTERNAL_TEAM_ROLES))
        .order_by(Client.created_at.asc())
    )
    users = result.scalars().all()
    return [_serialize_admin_user(user) for user in users]


@router.post("/admin/users/invite", response_model=AdminUserResponse, status_code=201)
async def invite_admin_user(
    body: AdminUserInviteRequest,
    admin: dict = Depends(require_permissions("team.manage")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Invite a new internal team user by email and persist the invite in the DB."""
    existing = await db.execute(select(Client).where(Client.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")

    user = Client(
        name=body.name,
        email=body.email,
        hashed_password=None,
        role=body.role,
          permissions=normalize_permissions(body.permissions) or get_default_permissions_for_role(body.role),
        plan="pro",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    token = await _issue_invite(user=user, db=db)
    await db.refresh(user)
    invite_url = _invite_url(token)

    import asyncio
    from app.services.email_service import send_team_invite_email

    asyncio.create_task(
        send_team_invite_email(
            to=user.email,
            name=user.name,
            invited_by=admin["email"],
            accept_url=invite_url,
        )
    )

    logger.info(f"Internal invite sent by {admin['email']} to {user.email} ({user.role})")
    return _serialize_admin_user(user, invite_url=invite_url, invite_code=token)


@router.post("/admin/users", response_model=AdminUserResponse, status_code=201)
async def create_admin_user(
    body: AdminUserCreateRequest,
    admin: dict = Depends(require_permissions("team.manage")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a DB-backed internal team login with email + password."""
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    existing = await db.execute(select(Client).where(Client.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")

    user = Client(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
          permissions=normalize_permissions(body.permissions) or get_default_permissions_for_role(body.role),
        plan="pro",
        is_active=True,
        invite_accepted_at=_now(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"Internal team user created by {admin['email']}: {user.email} ({user.role})")

    return _serialize_admin_user(user)


@router.patch("/admin/users/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: str,
    body: AdminUserUpdateRequest,
    admin: dict = Depends(require_permissions("team.manage")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Update an internal team member's role and permissions."""
    user = await db.get(Client, user_id)
    if not user or user.role not in INTERNAL_TEAM_ROLES:
        raise HTTPException(404, "Internal user not found")
    if user.role == "owner":
        raise HTTPException(400, "Owner permissions cannot be modified")

    updates = body.model_dump(exclude_none=True)
    next_role = updates.get("role", user.role)
    if next_role == "owner":
        raise HTTPException(400, "Owner role cannot be assigned from this endpoint")

    user.role = next_role
    if "permissions" in updates:
        user.permissions = normalize_permissions(updates["permissions"]) or get_default_permissions_for_role(next_role)
    elif "role" in updates:
        user.permissions = get_default_permissions_for_role(next_role)

    await db.commit()
    await db.refresh(user)
    logger.info(f"Internal user {user.email} permissions updated by {admin['email']}")
    return _serialize_admin_user(user)


@router.post("/admin/users/{user_id}/status", response_model=AdminUserResponse)
async def set_admin_user_status(
    user_id: str,
    body: AdminUserStatusRequest,
    admin: dict = Depends(require_permissions("team.manage")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Activate or deactivate an internal team user."""
    user = await db.get(Client, user_id)
    if not user or user.role not in INTERNAL_TEAM_ROLES:
        raise HTTPException(404, "Internal user not found")
    if str(user.id) == admin["client_id"] and not body.is_active:
        raise HTTPException(400, "You cannot deactivate your own account")
    if user.role == "owner" and not body.is_active:
        raise HTTPException(400, "The owner account cannot be deactivated")

    user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    logger.info(f"Internal user {user.email} active={user.is_active} updated by {admin['email']}")
    return _serialize_admin_user(user)


@router.post("/admin/users/{user_id}/send-reset", response_model=AdminUserResponse)
async def send_admin_reset(
    user_id: str,
    admin: dict = Depends(require_permissions("team.manage")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Send a reset link for an existing internal user, or re-send invite if pending."""
    user = await db.get(Client, user_id)
    if not user or user.role not in INTERNAL_TEAM_ROLES:
        raise HTTPException(404, "Internal user not found")

    import asyncio
    from app.services.email_service import send_password_reset_email, send_team_invite_email

    if not user.hashed_password or not user.invite_accepted_at:
        token = await _issue_invite(user=user, db=db)
        invite_url = _invite_url(token)
        asyncio.create_task(
            send_team_invite_email(
                to=user.email,
                name=user.name,
                invited_by=admin["email"],
                accept_url=invite_url,
            )
        )
        logger.info(f"Internal invite re-sent by {admin['email']} to {user.email}")
        await db.refresh(user)
        return _serialize_admin_user(user, invite_url=invite_url, invite_code=token)
    else:
        token = await _issue_password_reset(user=user, db=db)
        reset_url = _reset_url(token)
        asyncio.create_task(
            send_password_reset_email(
                to=user.email,
                name=user.name,
                reset_url=reset_url,
            )
        )
        logger.info(f"Internal reset sent by {admin['email']} to {user.email}")
        await db.refresh(user)
        return _serialize_admin_user(user, reset_url=reset_url, reset_code=token)


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
          permissions=get_effective_permissions(client.role, client.permissions),
    )

    logger.info(f"Demo token issued for {client.email}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
          "permissions": get_effective_permissions(client.role, client.permissions),
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

    client = await _ensure_owner_role(client, db)

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
          permissions=get_effective_permissions(client.role, client.permissions),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
          "permissions": get_effective_permissions(client.role, client.permissions),
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

    client = await _ensure_owner_role(client, db)

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
    client.password_reset_token_hash = None
    client.password_reset_expires_at = None
    await db.commit()

    logger.info(f"Password changed for {client.email}")

    return {"ok": True, "message": "Password changed successfully"}


# ── Admin Signup (requires special code) ────────────────────────────────────

class AdminSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    admin_code: str | None = None


@router.get("/admin-bootstrap-status", response_model=AdminBootstrapStatusResponse)
async def admin_bootstrap_status(
    db: AsyncSession = Depends(get_session),
) -> dict:
    internal_user_count = await _count_internal_users(db)
    has_owner = await _has_owner(db)
    return {
        "bootstrap_open": internal_user_count == 0,
        "has_owner": has_owner,
        "internal_user_count": internal_user_count,
    }


@router.post("/admin-signup", response_model=TokenResponse, status_code=201)
async def admin_signup(
    body: AdminSignupRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Bootstrap the very first owner account. Disabled after bootstrap."""
    if await _count_internal_users(db) > 0:
        raise HTTPException(403, "Internal account bootstrap is closed. Use an owner-issued invite.")

    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    result = await db.execute(
        select(Client).where(Client.email == body.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")

    client = Client(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        plan="pro",
        role="owner",
        is_active=True,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
    )

    logger.info(f"Owner bootstrap completed: {client.email} ({client.id})")

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": "admin",
    }


# ── Clerk SSO ────────────────────────────────────────────────────────────────

@router.post("/clerk-session", response_model=TokenResponse)
async def clerk_session(
    client: dict = Depends(get_current_client),
) -> dict:
    """Exchange a Clerk JWT for an Omniweb engine JWT.

    The frontend calls this after Clerk sign-in to get an engine-issued
    JWT that carries `client_id`, `plan`, and `role` — which the dashboard
    needs for all subsequent API calls.

    The `get_current_client` dependency already handles Clerk JWT
    verification and auto-provisioning, so by the time we get here the
    Client record is guaranteed to exist.
    """
    token = create_access_token(
        client_id=client["client_id"],
        email=client["email"],
        plan=client["plan"],
        role=client["role"],
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": client["client_id"],
        "email": client["email"],
        "plan": client["plan"],
        "role": client.get("role", "client"),
    }


# ── Account deletion ────────────────────────────────────────────────────────

@router.delete("/account")
async def delete_account(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Permanently delete the authenticated client's account and all associated data.

    Cascades to agent_config, calls, leads, phone numbers, etc.
    Internal staff (owner/admin/support) cannot self-delete via this endpoint.
    """
    client = await db.get(Client, current_client["client_id"])
    if not client:
        raise HTTPException(404, "Account not found")

    if is_internal_staff_role(client.role):
        raise HTTPException(400, "Internal staff accounts cannot be deleted via this endpoint")

    email = client.email
    client_id = str(client.id)

    # Use raw SQL DELETE so the DB-level ON DELETE CASCADE handles all child rows.
    # ORM db.delete() doesn't trigger DB cascades and fails on NOT NULL FKs.
    from sqlalchemy import text
    await db.execute(text("DELETE FROM clients WHERE id = :cid"), {"cid": client.id})
    await db.commit()

    logger.info(f"Account deleted: {email} ({client_id})")
    return {"ok": True, "message": "Account and all associated data have been permanently deleted"}

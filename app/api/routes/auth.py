"""Auth API — login, signup, token refresh, API key management.

Endpoints:
    POST /auth/signup    — create a new client + agent config
    POST /auth/login     — email + password → JWT
    POST /auth/refresh   — extend JWT lifetime
    POST /auth/api-key   — generate a new API key for the client
"""
from typing import Optional

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
)
from app.core.logging import get_logger
from app.models.models import AgentConfig, Client

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    client_id: str
    email: str
    plan: str


class ApiKeyResponse(BaseModel):
    api_key: str
    note: str = "Save this key — it cannot be retrieved again."


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new client account and return a JWT."""
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
        is_active=True,
    )
    db.add(client)
    await db.flush()

    # Create default agent config
    agent_config = AgentConfig(
        client_id=client.id,
        agent_name="AI Assistant",
        agent_greeting="Hello! How can I help you today?",
        system_prompt="You are a helpful AI assistant.",
        business_name=body.business_name or body.name,
        business_type=body.business_type,
    )
    db.add(agent_config)
    await db.commit()
    await db.refresh(client)

    # Issue JWT
    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
    )

    logger.info(f"New client signup: {client.email} ({client.id})")

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
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

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
    )

    logger.info(f"Client login: {client.email}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
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
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
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

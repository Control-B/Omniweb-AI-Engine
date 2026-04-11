"""Agent Config API — manage per-client AI agent settings.

When config is updated, the changes are synced to the ElevenLabs agent.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services import elevenlabs_service

logger = get_logger(__name__)
router = APIRouter(prefix="/agent-config", tags=["agent-config"])


class AgentConfigUpdate(BaseModel):
    agent_name: Optional[str] = None
    agent_greeting: Optional[str] = None
    voice_id: Optional[str] = None
    voice_stability: Optional[float] = None
    voice_similarity_boost: Optional[float] = None
    system_prompt: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    timezone: Optional[str] = None
    booking_url: Optional[str] = None
    business_hours: Optional[dict] = None
    services: Optional[list] = None
    after_hours_message: Optional[str] = None
    after_hours_sms_enabled: Optional[bool] = None
    allow_interruptions: Optional[bool] = None
    max_call_duration: Optional[int] = None
    widget_config: Optional[dict] = None


@router.get("/{client_id}")
async def get_config(
    client_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    # Tenant isolation: non-admin can only see own config
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, f"No agent config for client {client_id}")
    return {f: getattr(config, f) for f in AgentConfig.__table__.columns.keys()}


@router.put("/{client_id}")
async def upsert_config(
    client_id: str,
    body: AgentConfigUpdate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create or update the agent config for a client.

    If the client has an ElevenLabs agent, sync the changes to it.
    If no ElevenLabs agent exists yet, create one.
    """
    # Tenant isolation
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        config = AgentConfig(client_id=client_id)
        db.add(config)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(config, field, value)

    await db.flush()

    # Sync to ElevenLabs
    try:
        if config.elevenlabs_agent_id:
            # Update existing agent
            await elevenlabs_service.update_agent(
                config.elevenlabs_agent_id,
                name=f"{config.business_name} - {config.agent_name}",
                first_message=config.agent_greeting,
                system_prompt=config.system_prompt,
                voice_id=config.voice_id,
                voice_stability=config.voice_stability,
                voice_similarity_boost=config.voice_similarity_boost,
                max_duration_seconds=config.max_call_duration,
            )
            logger.info(f"Synced config to ElevenLabs agent {config.elevenlabs_agent_id}")
        else:
            # Create new ElevenLabs agent
            result_el = await elevenlabs_service.create_agent(
                name=f"{config.business_name} - {config.agent_name}",
                first_message=config.agent_greeting,
                system_prompt=config.system_prompt,
                voice_id=config.voice_id,
                voice_stability=config.voice_stability,
                voice_similarity_boost=config.voice_similarity_boost,
                max_duration_seconds=config.max_call_duration,
            )
            config.elevenlabs_agent_id = result_el["agent_id"]
            logger.info(f"Created ElevenLabs agent: {config.elevenlabs_agent_id}")
    except Exception as exc:
        logger.error(f"Failed to sync config to ElevenLabs: {exc}")
        # Don't fail the request — save config locally even if ElevenLabs is down

    await db.commit()
    await db.refresh(config)
    return {
        "ok": True,
        "client_id": client_id,
        "elevenlabs_agent_id": config.elevenlabs_agent_id,
    }


@router.get("/{client_id}/widget")
async def get_widget_embed(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the embeddable chat widget code for the client's agent.

    Public endpoint — no auth required (used by client websites).
    """
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config or not config.elevenlabs_agent_id:
        raise HTTPException(404, "No ElevenLabs agent configured")

    return {
        "agent_id": config.elevenlabs_agent_id,
        "embed_code": elevenlabs_service.get_widget_embed_code(config.elevenlabs_agent_id),
    }

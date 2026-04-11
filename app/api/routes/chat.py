"""Chat API — text chat proxy and widget configuration.

Endpoints:
    GET  /chat/widget/{client_id}     — get widget embed code
    GET  /chat/config/{client_id}     — get chat config (agent_id for frontend)
    POST /chat/conversations          — list text conversations for a client
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services import elevenlabs_service

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/widget/{client_id}")
async def get_widget(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the embeddable chat widget HTML for a client's agent.

    This is a public endpoint — used by the client's website to embed the widget.
    """
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config or not config.elevenlabs_agent_id:
        raise HTTPException(404, "No agent configured for this client")

    embed_code = elevenlabs_service.get_widget_embed_code(config.elevenlabs_agent_id)

    return {
        "agent_id": config.elevenlabs_agent_id,
        "embed_code": embed_code,
        "agent_name": config.agent_name,
    }


@router.get("/config/{client_id}")
async def get_chat_config(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get chat configuration for the frontend SDK integration.

    Returns the ElevenLabs agent_id so the frontend can connect directly
    via the ElevenLabs WebSocket or React SDK.
    """
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "No agent configured for this client")

    return {
        "agent_id": config.elevenlabs_agent_id,
        "agent_name": config.agent_name,
        "greeting": config.agent_greeting,
        "business_name": config.business_name,
    }


@router.get("/conversations")
async def list_chat_conversations(
    current_client: dict = Depends(get_current_client),
    page_size: int = Query(30, le=100),
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List text chat conversations for the authenticated client."""
    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.client_id == current_client["client_id"]
        )
    )
    config = result.scalar_one_or_none()
    if not config or not config.elevenlabs_agent_id:
        return {"conversations": [], "has_more": False}

    try:
        data = await elevenlabs_service.list_conversations(
            agent_id=config.elevenlabs_agent_id,
            page_size=page_size,
            cursor=cursor,
        )
        return data
    except Exception as exc:
        logger.error(f"Failed to list conversations: {exc}")
        return {"conversations": [], "has_more": False, "error": str(exc)}

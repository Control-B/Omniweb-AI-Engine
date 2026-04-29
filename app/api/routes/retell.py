"""Retell API — mint web call tokens for the browser SDK.

Public ``POST /api/retell/web-call`` accepts an optional ``client_id`` to select
the tenant's ``retell_agent_id``; otherwise the landing/demo agent from
``RETELL_LANDING_AGENT_ID`` is used.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services import retell_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/retell", tags=["retell"])


class WebCallRequest(BaseModel):
    client_id: str | None = None
    language: str | None = None  # reserved for per-session overrides


class WebCallResponse(BaseModel):
    access_token: str
    call_id: str | None = None
    agent_id: str


@router.post("/web-call", response_model=WebCallResponse)
async def create_web_call_session(
    req: WebCallRequest,
    db: AsyncSession = Depends(get_session),
):
    """Return a short-lived Retell access token for ``RetellWebClient.startCall``."""
    if not settings.retell_configured:
        raise HTTPException(status_code=503, detail="Retell is not configured")

    agent_id: str | None = None
    metadata: dict[str, Any] = {"source": "omniweb-web"}

    if req.client_id:
        try:
            cid = UUID(req.client_id)
        except ValueError:
            raise HTTPException(400, "Invalid client_id")
        result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == cid))
        config = result.scalar_one_or_none()
        if not config or not config.retell_agent_id:
            raise HTTPException(
                404,
                "No Retell agent linked to this client. Add retell_agent_id in agent settings.",
            )
        agent_id = config.retell_agent_id
        metadata["client_id"] = req.client_id
    else:
        agent_id = settings.RETELL_LANDING_AGENT_ID
        if not agent_id:
            raise HTTPException(
                503,
                "RETELL_LANDING_AGENT_ID is not set (required for anonymous web calls)",
            )
        if settings.LANDING_PAGE_CLIENT_ID:
            metadata["client_id"] = settings.LANDING_PAGE_CLIENT_ID

    if req.language:
        metadata["preferred_language"] = req.language

    try:
        data = await retell_service.create_web_call(agent_id=agent_id, metadata=metadata)
    except Exception as exc:
        logger.error("Retell web call error", error=str(exc))
        raise HTTPException(502, detail="Failed to start Retell session") from exc

    token = data.get("access_token")
    if not token:
        raise HTTPException(502, detail="Retell response missing access_token")

    return WebCallResponse(
        access_token=token,
        call_id=data.get("call_id"),
        agent_id=agent_id,
    )

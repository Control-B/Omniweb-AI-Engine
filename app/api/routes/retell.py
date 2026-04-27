"""Retell API — mint web call tokens for the browser SDK.

Public ``POST /api/retell/web-call`` mirrors the old LiveKit token route:
optional ``client_id`` selects the tenant's ``retell_agent_id``; otherwise the
landing/demo agent from ``RETELL_LANDING_AGENT_ID`` is used.
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
from app.models.models import AgentConfig, PhoneNumber
from app.services import retell_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/retell", tags=["retell"])


class WebCallRequest(BaseModel):
    client_id: str | None = None
    language: str | None = None  # reserved for per-session overrides


class PhoneCallRequest(BaseModel):
    client_id: str
    to_number: str
    language: str | None = None


class WebCallResponse(BaseModel):
    access_token: str
    call_id: str | None = None
    agent_id: str


class PhoneCallResponse(BaseModel):
    ok: bool
    call_id: str | None = None
    agent_id: str
    from_number: str
    to_number: str


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


def _clean_phone(value: str | None) -> str:
    return (value or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


@router.post("/phone-call", response_model=PhoneCallResponse)
async def create_phone_call_session(
    req: PhoneCallRequest,
    db: AsyncSession = Depends(get_session),
):
    """Start an outbound Retell telephone call to a shopper/customer number."""
    if not settings.retell_configured:
        raise HTTPException(status_code=503, detail="Retell is not configured")

    to_number = _clean_phone(req.to_number)
    if not to_number.startswith("+") or len(to_number) < 8:
        raise HTTPException(400, "Enter the customer phone number in E.164 format, e.g. +15551234567")

    try:
        cid = UUID(req.client_id)
    except ValueError:
        raise HTTPException(400, "Invalid client_id")

    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == cid))
    config = result.scalar_one_or_none()
    if not config or not config.retell_agent_id:
        raise HTTPException(404, "No Retell agent linked to this client. Add retell_agent_id in agent settings.")

    widget_config = config.widget_config or {}
    telephony = widget_config.get("ai_telephony") if isinstance(widget_config, dict) else {}
    from_number = _clean_phone((telephony or {}).get("phone_number"))
    if not from_number:
        number_result = await db.execute(
            select(PhoneNumber)
            .where(PhoneNumber.client_id == cid, PhoneNumber.is_active == True)
            .order_by(PhoneNumber.created_at.desc())
            .limit(1)
        )
        number = number_result.scalar_one_or_none()
        from_number = _clean_phone(number.phone_number if number else None)

    if not from_number:
        raise HTTPException(400, "Configure a Retell/Twilio phone number before starting AI Telephony calls.")

    handoff_phone = _clean_phone(config.handoff_phone)
    metadata: dict[str, Any] = {
        "source": "omniweb-ai-telephony",
        "client_id": req.client_id,
        "human_transfer_number": handoff_phone,
        "preferred_language": req.language or "",
    }
    dynamic_variables = {
        "business_name": config.business_name or "this store",
        "agent_name": config.agent_name or "Omniweb AI",
        "human_transfer_number": handoff_phone,
        "handoff_message": config.handoff_message,
        "telephony_mode": "outbound_call_us_widget",
    }

    try:
        data = await retell_service.create_phone_call(
            agent_id=config.retell_agent_id,
            from_number=from_number,
            to_number=to_number,
            metadata=metadata,
            dynamic_variables=dynamic_variables,
        )
    except Exception as exc:
        logger.error("Retell phone call error", error=str(exc))
        raise HTTPException(502, detail="Failed to start Retell phone call") from exc

    return PhoneCallResponse(
        ok=True,
        call_id=data.get("call_id"),
        agent_id=config.retell_agent_id,
        from_number=from_number,
        to_number=to_number,
    )

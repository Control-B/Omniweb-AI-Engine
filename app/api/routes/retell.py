"""Retell API — mint web call tokens for the browser SDK.

Public ``POST /api/retell/web-call`` accepts an optional ``client_id`` to select
the tenant's ``retell_agent_id``; otherwise the landing/demo agent from
``RETELL_LANDING_AGENT_ID`` is used.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, PhoneNumber
from app.services import retell_service
from app.services.retell_telephony_service import RetellTelephonyService, verify_retell_signature

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


async def _json_body(request: Request) -> dict[str, Any]:
    payload = await request.json()
    return payload if isinstance(payload, dict) else {"payload": payload}


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


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    x_retell_signature: str | None = Header(None),
    retell_signature: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    raw_body = await request.body()
    signature = x_retell_signature or retell_signature
    if not verify_retell_signature(raw_body, signature):
        raise HTTPException(401, "Invalid Retell webhook signature")
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid webhook payload")
    try:
        return await RetellTelephonyService(db).handle_webhook(payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        logger.error("Retell webhook handling failed", error=str(exc))
        raise HTTPException(502, "Unable to process Retell webhook") from exc


@router.post("/tool-call")
async def retell_tool_call(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    payload = await _json_body(request)
    try:
        return await RetellTelephonyService(db).handle_tool_call(payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        logger.error("Retell tool-call failed", error=str(exc))
        raise HTTPException(502, "Unable to process Retell tool call") from exc


@router.post("/call-start")
async def retell_call_start(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    payload = await _json_body(request)
    try:
        return await RetellTelephonyService(db).handle_call_start(payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/call-end")
async def retell_call_end(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    payload = await _json_body(request)
    try:
        return await RetellTelephonyService(db).handle_call_end(payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/escalate")
async def retell_escalate(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    payload = await _json_body(request)
    try:
        response = await RetellTelephonyService(db).handle_tool_call(
            {**payload, "message": payload.get("message") or "The caller requested human escalation."}
        )
        return {"ok": True, "escalation": response.get("escalation"), "actions": response.get("actions", [])}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

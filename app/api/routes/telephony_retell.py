"""Tenant-owned AI Telephony setup endpoints backed by Retell."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.services.retell_telephony_service import RetellTelephonyService, clean_phone

logger = get_logger(__name__)
router = APIRouter(prefix="/telephony/retell", tags=["telephony-retell"])


class RetellConfigPatch(BaseModel):
    human_escalation_phone: str | None = None
    fallback_email: str | None = None
    business_hours: dict[str, Any] | None = None
    trigger_keywords: list[str] | None = None
    retell_phone_number: str | None = None
    status: str | None = Field(None, pattern="^(active|disabled|provisioning|error)$")


class RetellTestCallRequest(BaseModel):
    to_number: str


def _tenant_id(current: dict) -> UUID:
    try:
        return UUID(str(current["client_id"]))
    except Exception as exc:
        raise HTTPException(401, "Invalid tenant session") from exc


@router.post("/provision")
async def provision_retell_telephony(
    body: RetellConfigPatch | None = None,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = RetellTelephonyService(db)
    try:
        return await service.provision(_tenant_id(current), config=(body.model_dump(exclude_none=True) if body else None))
    except Exception as exc:
        logger.error("Retell provision endpoint failed", error=str(exc))
        raise HTTPException(502, "Unable to provision AI Telephony") from exc


@router.get("/status")
async def get_retell_telephony_status(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = RetellTelephonyService(db)
    return await service.status(_tenant_id(current))


@router.patch("/config")
async def patch_retell_telephony_config(
    body: RetellConfigPatch,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = RetellTelephonyService(db)
    return await service.update_config(_tenant_id(current), body.model_dump(exclude_none=True))


@router.post("/test-call")
async def create_retell_test_call(
    body: RetellTestCallRequest,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = RetellTelephonyService(db)
    try:
        return await service.test_call(_tenant_id(current), clean_phone(body.to_number))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("Retell test call failed", error=str(exc))
        raise HTTPException(502, "Unable to start Retell test call") from exc

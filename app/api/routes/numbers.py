"""Phone Numbers API — provision and manage client phone numbers (Twilio).

AI answering is configured by connecting the purchased Twilio number to Retell.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, PhoneNumber
from app.services import sip_provisioning_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/numbers", tags=["numbers"])

PLAN_NUMBER_LIMITS = {
    "starter": 1,
    "growth": 3,
    "pro": 5,
    "agency": 50,
}


def _resolve_client_id(current_client: dict, client_id: str | None) -> str:
    if client_id and current_client.get("role") == "admin":
        return client_id
    return current_client["client_id"]


class ProvisionRequest(BaseModel):
    phone_number: str
    friendly_name: str
    client_id: Optional[str] = None


@router.get("/available")
async def list_available(
    area_code: Optional[str] = Query(None),
    country: str = Query("US"),
    limit: int = Query(20, le=50),
    number_type: str = Query("local"),
) -> dict:
    """Search available phone numbers from Twilio."""
    numbers = await sip_provisioning_service.list_available_numbers(
        area_code=area_code, country=country, limit=limit, number_type=number_type,
    )
    return {"numbers": numbers}


@router.post("", status_code=201)
async def provision_number(
    body: ProvisionRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Buy a Twilio number for the client."""
    cid = _resolve_client_id(current_client, body.client_id)

    plan = current_client.get("plan", "starter")
    max_numbers = PLAN_NUMBER_LIMITS.get(plan, 1)
    existing_count_result = await db.execute(
        select(PhoneNumber).where(PhoneNumber.client_id == cid)
    )
    existing_count = len(existing_count_result.scalars().all())
    if existing_count >= max_numbers:
        raise HTTPException(
            403,
            f"Your {plan} plan allows up to {max_numbers} phone number(s). "
            f"You currently have {existing_count}. Upgrade your plan to add more.",
        )

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == cid)
    )
    config = result.scalar_one_or_none()
    retell_agent_id = config.retell_agent_id if config else None

    number = await sip_provisioning_service.provision_new_number(
        db=db,
        client_id=cid,
        phone_number=body.phone_number,
        friendly_name=body.friendly_name,
        retell_agent_id=retell_agent_id,
    )
    return {
        "id": str(number.id),
        "phone_number": number.phone_number,
        "friendly_name": number.friendly_name,
        "twilio_sid": number.twilio_sid,
        "retell_agent_id": retell_agent_id,
        "hint": "Connect this Twilio number to your Retell agent for AI answering.",
    }


@router.get("")
async def list_numbers(
    current_client: dict = Depends(get_current_client),
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    cid = _resolve_client_id(current_client, client_id)
    result = await db.execute(
        select(PhoneNumber).where(PhoneNumber.client_id == cid)
    )
    numbers = result.scalars().all()
    return {
        "numbers": [
            {
                "id": str(n.id),
                "phone_number": n.phone_number,
                "friendly_name": n.friendly_name,
                "is_active": n.is_active,
                "twilio_sid": n.twilio_sid,
                "mode": n.mode,
                "forward_to": n.forward_to,
            }
            for n in numbers
        ]
    }


@router.delete("/{number_id}")
async def deprovision_number(
    number_id: UUID,
    release_twilio: bool = Query(False),
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    number = await db.get(PhoneNumber, number_id)
    if not number:
        raise HTTPException(404, "Phone number not found")
    if current_client.get("role") != "admin" and str(number.client_id) != current_client["client_id"]:
        raise HTTPException(404, "Phone number not found")
    await sip_provisioning_service.deprovision_number(
        db, number, release_twilio_number=release_twilio
    )
    return {"ok": True, "phone_number": number.phone_number}


class SetModeRequest(BaseModel):
    mode: str
    forward_to: Optional[str] = None


@router.post("/{number_id}/mode")
async def set_number_mode(
    number_id: UUID,
    body: SetModeRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if body.mode not in ("ai", "forward"):
        raise HTTPException(400, "mode must be 'ai' or 'forward'")
    if body.mode == "forward" and not body.forward_to:
        raise HTTPException(400, "forward_to is required when mode is 'forward'")

    number = await db.get(PhoneNumber, number_id)
    if not number:
        raise HTTPException(404, "Phone number not found")
    if current_client.get("role") != "admin" and str(number.client_id) != current_client["client_id"]:
        raise HTTPException(404, "Phone number not found")

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == number.client_id)
    )
    config = result.scalar_one_or_none()
    retell_agent_id = config.retell_agent_id if config else None

    try:
        await sip_provisioning_service.set_number_mode(
            db,
            number,
            mode=body.mode,
            forward_to=body.forward_to,
            retell_agent_id=retell_agent_id,
        )
    except Exception as exc:
        raise HTTPException(500, f"Failed to switch mode: {exc}") from exc

    return {
        "ok": True,
        "phone_number": number.phone_number,
        "mode": number.mode,
        "forward_to": number.forward_to,
    }


@router.post("/{number_id}/assign-agent")
async def assign_number_to_agent(
    number_id: UUID,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Inbound AI routing is completed in Retell when linking the Twilio number."""
    number = await db.get(PhoneNumber, number_id)
    if not number:
        raise HTTPException(404, "Phone number not found")
    if current_client.get("role") != "admin" and str(number.client_id) != current_client["client_id"]:
        raise HTTPException(404, "Phone number not found")

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == number.client_id)
    )
    config = result.scalar_one_or_none()
    if not config or not config.retell_agent_id:
        raise HTTPException(400, "Client has no Retell agent configured")

    return {
        "ok": True,
        "phone_number": number.phone_number,
        "retell_agent_id": config.retell_agent_id,
        "message": "Finish phone binding in the Retell dashboard (connect this Twilio DID to the agent).",
    }

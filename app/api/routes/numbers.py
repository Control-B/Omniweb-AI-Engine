"""Phone Numbers API — provision and manage client phone numbers."""
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
from app.models.models import AgentConfig, PhoneNumber, Client
from app.services import sip_provisioning_service, elevenlabs_service, retell_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/numbers", tags=["numbers"])

# Plan limits for phone numbers
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
    client_id: Optional[str] = None  # admin can specify; otherwise uses caller's


@router.get("/available")
async def list_available(
    area_code: Optional[str] = Query(None),
    country: str = Query("US"),
    limit: int = Query(20, le=50),
    number_type: str = Query("local"),  # "local" or "toll_free"
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
    """Provision a phone number for the client's configured telephony provider."""
    cid = _resolve_client_id(current_client, body.client_id)

    # ── Plan enforcement: check number limit ──────────────────────────
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

    # Look up the client's ElevenLabs agent ID
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == cid)
    )
    config = result.scalar_one_or_none()
    elevenlabs_agent_id = config.elevenlabs_agent_id if config else None
    retell_agent_id = config.retell_agent_id if config else None
    retell_agent_version = config.retell_agent_version if config else None
    telephony_provider = config.telephony_provider if config else "retell"

    number = await sip_provisioning_service.provision_new_number(
        db=db,
        client_id=cid,
        phone_number=body.phone_number,
        friendly_name=body.friendly_name,
        elevenlabs_agent_id=elevenlabs_agent_id,
        retell_agent_id=retell_agent_id,
        retell_agent_version=retell_agent_version,
        telephony_provider=telephony_provider,
    )
    return {
        "id": str(number.id),
        "phone_number": number.phone_number,
        "friendly_name": number.friendly_name,
        "provider": number.provider,
        "twilio_sid": number.twilio_sid,
        "elevenlabs_phone_number_id": number.elevenlabs_phone_number_id,
        "retell_phone_number_id": number.retell_phone_number_id,
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
                "provider": n.provider,
                "twilio_sid": n.twilio_sid,
                "elevenlabs_phone_number_id": n.elevenlabs_phone_number_id,
                "retell_phone_number_id": n.retell_phone_number_id,
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
    """Remove a phone number from ElevenLabs and optionally release from Twilio."""
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
    mode: str  # "ai" or "forward"
    forward_to: Optional[str] = None  # required when mode is "forward"


@router.post("/{number_id}/mode")
async def set_number_mode(
    number_id: UUID,
    body: SetModeRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Switch a phone number between AI agent mode and call forwarding mode."""
    if body.mode not in ("ai", "forward"):
        raise HTTPException(400, "mode must be 'ai' or 'forward'")
    if body.mode == "forward" and not body.forward_to:
        raise HTTPException(400, "forward_to is required when mode is 'forward'")

    number = await db.get(PhoneNumber, number_id)
    if not number:
        raise HTTPException(404, "Phone number not found")
    if current_client.get("role") != "admin" and str(number.client_id) != current_client["client_id"]:
        raise HTTPException(404, "Phone number not found")

    # Get agent ID for switching back to AI mode
    elevenlabs_agent_id = None
    retell_agent_id = None
    retell_agent_version = None
    if body.mode == "ai":
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.client_id == number.client_id)
        )
        config = result.scalar_one_or_none()
        elevenlabs_agent_id = config.elevenlabs_agent_id if config else None
        retell_agent_id = config.retell_agent_id if config else None
        retell_agent_version = config.retell_agent_version if config else None

    try:
        await sip_provisioning_service.set_number_mode(
            db, number,
            mode=body.mode,
            forward_to=body.forward_to,
            elevenlabs_agent_id=elevenlabs_agent_id,
            retell_agent_id=retell_agent_id,
            retell_agent_version=retell_agent_version,
        )
    except Exception as exc:
        raise HTTPException(500, f"Failed to switch mode: {exc}")

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
    """Assign (or reassign) a phone number to the client's active telephony agent."""
    number = await db.get(PhoneNumber, number_id)
    if not number:
        raise HTTPException(404, "Phone number not found")
    if current_client.get("role") != "admin" and str(number.client_id) != current_client["client_id"]:
        raise HTTPException(404, "Phone number not found")

    # Get client's agent
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == number.client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(400, "Client has no agent configuration")

    if number.provider == "retell":
        if not config.retell_agent_id:
            raise HTTPException(400, "Client has no Retell agent configured")
        await retell_service.update_phone_number(
            number.phone_number,
            agent_id=config.retell_agent_id,
            agent_version=config.retell_agent_version,
            nickname=number.friendly_name,
        )
        return {
            "ok": True,
            "phone_number": number.phone_number,
            "provider": number.provider,
            "agent_id": config.retell_agent_id,
        }

    if not config.elevenlabs_agent_id:
        raise HTTPException(400, "Client has no ElevenLabs agent configured")

    if not number.elevenlabs_phone_number_id:
        raise HTTPException(400, "Number not imported into ElevenLabs yet")

    await elevenlabs_service.assign_phone_to_agent(
        number.elevenlabs_phone_number_id,
        config.elevenlabs_agent_id,
    )
    return {
        "ok": True,
        "phone_number": number.phone_number,
        "provider": number.provider,
        "agent_id": config.elevenlabs_agent_id,
    }

"""Phone Numbers API — provision and manage client phone numbers.

Flow: Buy from Twilio → Import into ElevenLabs → Assign to agent.
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
from app.services import sip_provisioning_service, elevenlabs_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/numbers", tags=["numbers"])


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
) -> dict:
    """Search available phone numbers from Twilio."""
    numbers = await sip_provisioning_service.list_available_numbers(
        area_code=area_code, country=country, limit=limit
    )
    return {"numbers": numbers}


@router.post("", status_code=201)
async def provision_number(
    body: ProvisionRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Buy a Twilio number and import it into ElevenLabs for the client's agent."""
    cid = _resolve_client_id(current_client, body.client_id)
    # Look up the client's ElevenLabs agent ID
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == cid)
    )
    config = result.scalar_one_or_none()
    elevenlabs_agent_id = config.elevenlabs_agent_id if config else None

    number = await sip_provisioning_service.provision_new_number(
        db=db,
        client_id=cid,
        phone_number=body.phone_number,
        friendly_name=body.friendly_name,
        elevenlabs_agent_id=elevenlabs_agent_id,
    )
    return {
        "id": str(number.id),
        "phone_number": number.phone_number,
        "friendly_name": number.friendly_name,
        "twilio_sid": number.twilio_sid,
        "elevenlabs_phone_number_id": number.elevenlabs_phone_number_id,
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
                "elevenlabs_phone_number_id": n.elevenlabs_phone_number_id,
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


@router.post("/{number_id}/assign-agent")
async def assign_number_to_agent(
    number_id: UUID,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Assign (or reassign) a phone number to the client's ElevenLabs agent."""
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
    if not config or not config.elevenlabs_agent_id:
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
        "agent_id": config.elevenlabs_agent_id,
    }

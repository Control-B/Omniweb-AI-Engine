"""Templates API — public endpoint for listing available agent templates.

Clients can browse templates during signup or when reconfiguring their agent.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.models import AgentTemplate

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
async def list_public_templates(
    industry: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List active templates available for clients to choose from."""
    q = select(AgentTemplate).where(AgentTemplate.is_active == True)
    if industry:
        q = q.where(AgentTemplate.industry == industry)
    q = q.order_by(AgentTemplate.name)
    result = await db.execute(q)
    templates = result.scalars().all()

    return {
        "templates": [
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "industry": t.industry,
                "agent_name": t.agent_name,
                "is_default": t.is_default,
            }
            for t in templates
        ]
    }

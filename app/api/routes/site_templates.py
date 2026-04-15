"""Site template instances API.

Persist client-specific website instances created from coded dashboard templates.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_session
from app.core.auth import get_current_client, is_internal_staff_role
from app.models.models import SiteTemplateInstance

router = APIRouter(prefix="/site-templates", tags=["site-templates"])

VALID_STATUSES = {"draft", "published", "archived"}


class SiteTemplateInstanceCreate(BaseModel):
    client_id: Optional[str] = None
    name: str
    site_slug: str
    public_slug: Optional[str] = None
    template_slug: str
    status: str = "draft"
    content: dict = Field(default_factory=dict)
    theme_overrides: dict = Field(default_factory=dict)
    agent_embed_config: dict = Field(default_factory=dict)


class SiteTemplateInstanceUpdate(BaseModel):
    name: Optional[str] = None
    site_slug: Optional[str] = None
    public_slug: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    content: Optional[dict] = None
    theme_overrides: Optional[dict] = None
    agent_embed_config: Optional[dict] = None


def _resolve_client_scope(current_client: dict, requested_client_id: str | None) -> str:
    if requested_client_id and is_internal_staff_role(current_client.get("role")):
        return requested_client_id
    return current_client["client_id"]


def _serialize(instance: SiteTemplateInstance) -> dict:
    return {
        "id": str(instance.id),
        "client_id": str(instance.client_id),
        "name": instance.name,
        "site_slug": instance.site_slug,
        "public_slug": instance.public_slug,
        "template_slug": instance.template_slug,
        "status": instance.status,
        "is_active": instance.is_active,
        "content": instance.content or {},
        "theme_overrides": instance.theme_overrides or {},
        "agent_embed_config": instance.agent_embed_config or {},
        "created_at": instance.created_at.isoformat() if instance.created_at else None,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
    }


@router.get("")
async def list_site_template_instances(
    client_id: str | None = Query(None),
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    scoped_client_id = _resolve_client_scope(current_client, client_id)
    result = await db.execute(
        select(SiteTemplateInstance)
        .where(SiteTemplateInstance.client_id == scoped_client_id)
        .order_by(SiteTemplateInstance.updated_at.desc())
    )
    instances = result.scalars().all()
    return {"instances": [_serialize(instance) for instance in instances]}


@router.post("", status_code=201)
async def create_site_template_instance(
    body: SiteTemplateInstanceCreate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    scoped_client_id = _resolve_client_scope(current_client, body.client_id)
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Expected one of: {', '.join(sorted(VALID_STATUSES))}")

    instance = SiteTemplateInstance(
        client_id=scoped_client_id,
        name=body.name,
        site_slug=body.site_slug,
        public_slug=body.public_slug or body.site_slug,
        template_slug=body.template_slug,
        status=body.status,
        content=body.content,
        theme_overrides=body.theme_overrides,
        agent_embed_config=body.agent_embed_config,
    )
    db.add(instance)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "A site with this slug already exists for this client") from exc
    await db.refresh(instance)
    return _serialize(instance)


@router.get("/public/{public_slug}")
async def get_public_site_template_instance(
    public_slug: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    result = await db.execute(
        select(SiteTemplateInstance).where(
            SiteTemplateInstance.public_slug == public_slug,
            SiteTemplateInstance.status == "published",
            SiteTemplateInstance.is_active == True,
        )
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(404, "Published site not found")
    return _serialize(instance)


@router.get("/{instance_id}")
async def get_site_template_instance(
    instance_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    instance = await db.get(SiteTemplateInstance, instance_id)
    if not instance:
        raise HTTPException(404, "Site template instance not found")
    if str(instance.client_id) != current_client["client_id"] and not is_internal_staff_role(current_client.get("role")):
        raise HTTPException(403, "Not authorized to access this site template instance")
    return _serialize(instance)


@router.put("/{instance_id}")
async def update_site_template_instance(
    instance_id: str,
    body: SiteTemplateInstanceUpdate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    instance = await db.get(SiteTemplateInstance, instance_id)
    if not instance:
        raise HTTPException(404, "Site template instance not found")
    if str(instance.client_id) != current_client["client_id"] and not is_internal_staff_role(current_client.get("role")):
        raise HTTPException(403, "Not authorized to update this site template instance")

    payload = body.model_dump(exclude_none=True)
    if "status" in payload and payload["status"] not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Expected one of: {', '.join(sorted(VALID_STATUSES))}")

    for field, value in payload.items():
        setattr(instance, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "A site with this slug already exists for this client") from exc
    await db.refresh(instance)
    return _serialize(instance)


@router.delete("/{instance_id}")
async def delete_site_template_instance(
    instance_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    instance = await db.get(SiteTemplateInstance, instance_id)
    if not instance:
        raise HTTPException(404, "Site template instance not found")
    if str(instance.client_id) != current_client["client_id"] and not is_internal_staff_role(current_client.get("role")):
        raise HTTPException(403, "Not authorized to delete this site template instance")

    await db.delete(instance)
    await db.commit()
    return {"ok": True}

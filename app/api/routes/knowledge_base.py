"""Knowledge base API — legacy ElevenLabs KB removed.

Attach documents and structured knowledge to your Retell agent in the Retell
dashboard (or via Retell APIs). Omniweb will add first-party KB storage here
when we wire file ingestion to Retell programmatically.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services.url_knowledge_service import UrlKnowledgeService

logger = get_logger(__name__)
router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


class TextCreateRequest(BaseModel):
    text: str
    name: Optional[str] = None


class UrlCreateRequest(BaseModel):
    url: str
    name: Optional[str] = None


@router.get("")
async def list_documents(
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List URL-derived knowledge snapshots for this tenant."""
    try:
        client_id = uuid.UUID(str(current_client["client_id"]))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid client id in auth context") from exc
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client_id).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        return {"documents": []}
    docs = []
    website_domain = (config.website_domain or "").strip()
    if website_domain:
        docs.append(
            {
                "type": "website_url",
                "name": "Merchant Website",
                "url": website_domain,
                "has_ingested_context": bool((config.custom_context or "").strip()),
            }
        )
    return {"documents": docs}


@router.post("/text", status_code=501)
async def create_from_text(
    body: TextCreateRequest,
    current_client: dict = Depends(get_current_client),
):
    _ = body
    _ = current_client
    raise HTTPException(
        status_code=501,
        detail="Knowledge uploads are configured in the Retell dashboard for your agent.",
    )


@router.post("/url")
async def create_from_url(
    body: UrlCreateRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
):
    """Ingest website URL content into tenant context for RAG-grounded replies."""
    target_url = (body.url or "").strip()
    if not target_url:
        raise HTTPException(status_code=400, detail="url is required")

    try:
        client_id = uuid.UUID(str(current_client["client_id"]))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid client id in auth context") from exc
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client_id).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found for client")

    try:
        ingest = await UrlKnowledgeService.ingest_website(target_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("URL knowledge ingestion failed", error=str(exc), url=target_url)
        raise HTTPException(status_code=502, detail="Failed to ingest website URL") from exc

    summary = ingest.get("summary") or ""
    if not summary:
        raise HTTPException(status_code=422, detail="No readable knowledge extracted from URL")

    config.website_domain = ingest.get("source_url") or target_url
    config.custom_context = summary
    await db.flush()

    return {
        "ok": True,
        "name": body.name or "Merchant Website",
        "url": config.website_domain,
        "pages_crawled": ingest.get("pages_crawled", 0),
        "summary_chars": len(summary),
        "message": "Website knowledge ingested and attached to tenant context.",
    }


@router.post("/file", status_code=501)
async def create_from_file(
    current_client: dict = Depends(get_current_client),
):
    _ = current_client
    raise HTTPException(
        status_code=501,
        detail="Knowledge uploads are configured in the Retell dashboard for your agent.",
    )


@router.delete("/{doc_id}", status_code=501)
async def delete_document(
    doc_id: str,
    current_client: dict = Depends(get_current_client),
):
    _ = doc_id
    _ = current_client
    raise HTTPException(
        status_code=501,
        detail="Manage knowledge documents in the Retell dashboard.",
    )

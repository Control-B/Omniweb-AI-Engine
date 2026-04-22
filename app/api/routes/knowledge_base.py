"""Knowledge base API — legacy ElevenLabs KB removed.

Attach documents and structured knowledge to your Retell agent in the Retell
dashboard (or via Retell APIs). Omniweb will add first-party KB storage here
when we wire file ingestion to Retell programmatically.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.auth import get_current_client
from app.core.logging import get_logger

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
) -> dict:
    """List KB documents (empty — use Retell dashboard for now)."""
    _ = current_client
    return {"documents": []}


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


@router.post("/url", status_code=501)
async def create_from_url(
    body: UrlCreateRequest,
    current_client: dict = Depends(get_current_client),
):
    _ = body
    _ = current_client
    raise HTTPException(
        status_code=501,
        detail="Knowledge uploads are configured in the Retell dashboard for your agent.",
    )


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

"""Knowledge Base API — upload and manage documents for the AI agent.

Endpoints:
    GET    /knowledge-base                — list KB documents
    POST   /knowledge-base/text           — create from raw text
    POST   /knowledge-base/url            — create from URL
    POST   /knowledge-base/file           — upload a file (PDF, TXT, DOCX)
    DELETE /knowledge-base/{doc_id}       — delete a document
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services import elevenlabs_service

logger = get_logger(__name__)
router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc", ".md", ".csv", ".html"}


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
    """List all knowledge base documents."""
    docs = await elevenlabs_service.list_knowledge_base()
    return {"documents": docs}


@router.post("/text", status_code=201)
async def create_from_text(
    body: TextCreateRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a KB document from raw text."""
    if not body.text.strip():
        raise HTTPException(400, "Text content cannot be empty")

    doc = await elevenlabs_service.create_kb_from_text(
        text=body.text,
        name=body.name,
    )

    # Auto-attach to agent if they have one
    await _attach_kb_to_agent(db, current_client["client_id"], doc["id"])

    logger.info(f"KB text doc created: {doc['id']} for client {current_client['client_id']}")
    return doc


@router.post("/url", status_code=201)
async def create_from_url(
    body: UrlCreateRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a KB document by scraping a URL."""
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    doc = await elevenlabs_service.create_kb_from_url(
        url=body.url,
        name=body.name,
    )

    await _attach_kb_to_agent(db, current_client["client_id"], doc["id"])

    logger.info(f"KB URL doc created: {doc['id']} for client {current_client['client_id']}")
    return doc


@router.post("/file", status_code=201)
async def create_from_file(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Upload a file to the knowledge base (PDF, TXT, DOCX, etc.)."""
    # Validate extension
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB")

    doc = await elevenlabs_service.create_kb_from_file(
        file_content=content,
        filename=file.filename or "upload",
        name=name,
    )

    await _attach_kb_to_agent(db, current_client["client_id"], doc["id"])

    logger.info(f"KB file doc created: {doc['id']} ({file.filename}) for client {current_client['client_id']}")
    return doc


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_client: dict = Depends(get_current_client),
) -> dict:
    """Delete a knowledge base document."""
    success = await elevenlabs_service.delete_kb_document(doc_id)
    if not success:
        raise HTTPException(500, "Failed to delete document")

    logger.info(f"KB doc deleted: {doc_id}")
    return {"ok": True, "message": "Document deleted"}


async def _attach_kb_to_agent(
    db: AsyncSession,
    client_id: str,
    kb_doc_id: str,
) -> None:
    """Auto-attach a new KB doc to the client's ElevenLabs agent."""
    try:
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.client_id == client_id)
        )
        config = result.scalar_one_or_none()
        if config and config.elevenlabs_agent_id:
            # Get current KB docs on the agent, add the new one
            await elevenlabs_service.update_agent(
                agent_id=config.elevenlabs_agent_id,
                knowledge_base_ids=[kb_doc_id],
            )
            # Store the KB ID on the config for reference
            if not config.elevenlabs_kb_id:
                config.elevenlabs_kb_id = kb_doc_id
            await db.commit()
    except Exception as e:
        logger.warning(f"Could not auto-attach KB doc {kb_doc_id} to agent: {e}")

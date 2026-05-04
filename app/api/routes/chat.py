"""Chat API — text chat proxy, welcome audio, and widget configuration.

Endpoints:
    POST /chat/welcome-audio         — synthesize welcome audio for frontend
    GET  /chat/widget/{client_id}     — get widget embed code
    GET  /chat/config/{client_id}     — get chat config (agent_id for frontend)
    POST /chat/conversations          — list text conversations for a client
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.api.deps import get_session
from app.api.routes.deepgram import (
    VoiceAgentBootstrapRequest,
    VoiceAgentSessionCompleteRequest,
    run_voice_agent_bootstrap,
    voice_agent_session_complete,
)
from app.core.auth import get_current_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services import elevenlabs_service
from app.services.assistant_scheduling_service import (
    build_email_request_payload_from_turns,
    send_requested_email,
)
from app.services.omniweb_brain_service import BrainRequest, OmniwebBrainService
from app.services.saas_workspace_service import resolve_client_by_public_identifier

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/chat", tags=["chat"])

# Canonical browser path for Deepgram bootstrap (some CDNs/WAFs block ``/api/deepgram/...`` POST).
_VOICE_BOOTSTRAP_PATH = "/api/chat/voice-agent/bootstrap"


@router.post("/voice-agent/bootstrap")
async def voice_agent_bootstrap_public(
    req: VoiceAgentBootstrapRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Mint Deepgram JWT + Voice Agent settings for the embed widget (alias of deepgram route)."""
    return await run_voice_agent_bootstrap(req, db, request)


@router.post("/voice-agent/session-complete")
async def voice_agent_session_complete_public(
    req: VoiceAgentSessionCompleteRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Persist and post-process completed voice sessions from the embed widget."""
    return await voice_agent_session_complete(req, db)


class WelcomeAudioRequest(BaseModel):
    text: str
    language: str | None = None
    voice_id: str | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRespondRequest(BaseModel):
    client_id: str | None = None
    messages: list[ChatMessage]
    metadata: dict | None = None


@router.post("/welcome-audio")
async def get_welcome_audio(body: WelcomeAudioRequest) -> Response:
    """Public endpoint to synthesize short welcome audio for the widget."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Text is required")
    if len(text) > 400:
        raise HTTPException(400, "Text must be 400 characters or fewer")

    try:
        audio_bytes = await elevenlabs_service.synthesize_speech(
            text=text,
            language=body.language,
            voice_id=body.voice_id,
        )
    except Exception as exc:
        logger.error(f"Failed to synthesize welcome audio: {exc}")
        raise HTTPException(502, "Failed to synthesize welcome audio") from exc

    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/respond")
async def chat_respond(
    body: ChatRespondRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Shared-brain text chat endpoint used by website chat clients."""
    raw_id = (body.client_id or settings.LANDING_PAGE_CLIENT_ID or "").strip()
    if not raw_id:
        raise HTTPException(400, "client_id is required")

    client = await resolve_client_by_public_identifier(db, raw_id)
    if not client:
        raise HTTPException(404, "No client found for client_id or widget key")

    user_message = ""
    for message in reversed(body.messages):
        if message.role.lower() == "user" and message.content.strip():
            user_message = message.content.strip()
            break
    if not user_message:
        raise HTTPException(400, "A user message is required")

    try:
        response = await OmniwebBrainService(db).run(
            BrainRequest(
                tenant_id=client.id,
                channel_type="chat",
                user_message=user_message,
                metadata=body.metadata or {},
            )
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    metadata = body.metadata or {}
    conversation_id = str(
        metadata.get("session_id")
        or metadata.get("sessionId")
        or metadata.get("conversation_id")
        or metadata.get("conversationId")
        or f"chat-{client.id}"
    )
    turns = [
        {"role": message.role.lower(), "content": message.content.strip()}
        for message in body.messages
        if message.content and message.content.strip()
    ]
    # Include the just-generated assistant reply so a single-shot send works
    # when the visitor's prior turn had the email and intent.
    if response.response_text:
        turns.append({"role": "assistant", "content": response.response_text})
    email_status = None
    email_payload = build_email_request_payload_from_turns(
        tenant_id=client.id,
        conversation_id=conversation_id,
        turns=turns,
        source_url=metadata.get("page_url") or metadata.get("sourceUrl") or metadata.get("source_url"),
    )
    if email_payload:
        try:
            email_status = await send_requested_email(db, email_payload)
            await db.commit()
            response.actions.append(
                {
                    "type": "send_email_notification",
                    "payload": {
                        "emailStatus": email_status,
                        "recipient": email_payload.visitor_email,
                    },
                }
            )
        except Exception as exc:
            logger.error("Text chat email request failed", client_id=str(client.id), error=str(exc))

    return {
        "response": response.response_text,
        "actions": response.actions,
        "escalation": response.escalation,
        "lead_fields": response.lead_fields,
        "email_status": email_status,
    }


@router.get("/languages")
async def get_chat_languages() -> dict:
    """Return the public language and voice options for the landing widget."""
    return {
        "default_language": elevenlabs_service._normalize_language_code(
            elevenlabs_service.settings.ELEVENLABS_DEFAULT_LANGUAGE
        ),
        "languages": elevenlabs_service.get_language_options(),
    }


@router.get("/diagnostics/email-log/{client_id}")
async def email_log_diagnostics(
    client_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return the most recent EmailLog rows for a tenant.

    Use this to confirm the assistant actually attempted to send an email
    after a conversation. ``status`` will be ``sent`` (Resend accepted the
    payload) or ``failed`` (Resend rejected — see ``error_message``). If no
    rows appear after a conversation in which you asked the agent to email
    you, the assistant never reached the send step (the API logs will say
    ``VOICE_EMAIL_NOT_SENT`` with the reason).
    """
    from app.models.models import EmailLog

    client = await resolve_client_by_public_identifier(db, client_id)
    if not client:
        raise HTTPException(404, "No client found for client_id or widget key")

    rows = (
        await db.execute(
            select(EmailLog)
            .where(EmailLog.tenant_id == client.id)
            .order_by(EmailLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "client_id": str(client.id),
        "count": len(rows),
        "logs": [
            {
                "id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "recipient": row.recipient,
                "subject": row.subject,
                "type": row.type,
                "provider": row.provider,
                "status": row.status,
                "conversation_id": row.conversation_id,
                "error_message": row.error_message,
            }
            for row in rows
        ],
    }


@router.get("/diagnostics/email-backend")
async def email_backend_diagnostics() -> dict:
    """Public-safe email backend status — confirms whether the API container can send.

    No secrets are returned. Use this to verify Resend is wired into the
    deployed API service: ``curl https://<your-api>/api/chat/diagnostics/email-backend``.
    """
    from app.services import email_service

    backend = email_service._email_backend()
    platform_from = getattr(email_service.settings, "RESEND_FROM_EMAIL", "") or ""
    identity = await email_service.resend_sender_identity_status(platform_from or None)
    return {
        "backend": backend,  # "resend" | "smtp" | "none"
        "resend_api_key_present": bool(getattr(email_service.settings, "RESEND_API_KEY", "")),
        "smtp_host_present": bool(getattr(email_service.settings, "SMTP_HOST", "")),
        "platform_from_configured": bool(platform_from),
        "platform_from_domain": identity.get("domain"),
        "platform_from_status": identity.get("status"),
        "platform_from_verified": identity.get("verified"),
    }


@router.get("/widget/{client_id}")
async def get_widget(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the embeddable chat widget HTML for a client's agent.

    This is a public endpoint — used by the client's website to embed the widget.
    """
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config or not config.elevenlabs_agent_id:
        raise HTTPException(404, "No agent configured for this client")

    embed_data = elevenlabs_service.get_widget_embed_code(config.elevenlabs_agent_id)

    return {
        "agent_id": config.elevenlabs_agent_id,
        "embed_code": embed_data["iframe"],
        "legacy_embed_code": embed_data["legacy"],
        "widget_url": embed_data["widget_url"],
        "agent_name": config.agent_name,
    }


@router.get("/config/{client_id}")
async def get_chat_config(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get chat configuration for the frontend SDK integration.

    Returns the ElevenLabs agent_id so the frontend can connect directly
    via the ElevenLabs WebSocket or React SDK.
    """
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "No agent configured for this client")

    return {
        "agent_id": config.elevenlabs_agent_id,
        "agent_name": config.agent_name,
        "greeting": config.agent_greeting,
        "business_name": config.business_name,
    }


@router.get("/conversations")
async def list_chat_conversations(
    current_client: dict = Depends(get_current_client),
    page_size: int = Query(30, le=100),
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List text chat conversations for the authenticated client."""
    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.client_id == current_client["client_id"]
        )
    )
    config = result.scalar_one_or_none()
    if not config or not config.elevenlabs_agent_id:
        return {"conversations": [], "has_more": False}

    try:
        data = await elevenlabs_service.list_conversations(
            agent_id=config.elevenlabs_agent_id,
            page_size=page_size,
            cursor=cursor,
        )
        return data
    except Exception as exc:
        logger.error(f"Failed to list conversations: {exc}")
        return {"conversations": [], "has_more": False, "error": str(exc)}

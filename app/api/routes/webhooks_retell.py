"""Retell webhook handler — call_ended / call_analyzed → Call + Transcript rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, Call, Transcript
from app.services import retell_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/webhooks/retell", tags=["webhooks"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _call_external_id(call_obj: dict[str, Any]) -> str | None:
    return (
        call_obj.get("call_id")
        or call_obj.get("id")
        or call_obj.get("call_sid")
    )


async def _resolve_client_for_agent(agent_id: str | None) -> UUID | None:
    if not agent_id:
        return None
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.retell_agent_id == agent_id)
        )
        cfg = result.scalar_one_or_none()
        if cfg:
            return cfg.client_id
    return None


@router.post("")
async def retell_webhook(request: Request, db: AsyncSession = Depends(get_session)):
    raw_bytes = await request.body()
    raw_text = raw_bytes.decode("utf-8")

    sig = request.headers.get("x-retell-signature") or request.headers.get("X-Retell-Signature")
    if settings.RETELL_API_KEY and sig:
        if not retell_service.verify_webhook_signature(
            raw_body=raw_text,
            signature_header=sig,
            api_key=settings.RETELL_API_KEY,
        ):
            logger.warning("Invalid Retell webhook signature")
            raise HTTPException(401, "Invalid signature")

    try:
        payload: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Invalid JSON") from exc

    event = payload.get("event")
    call_obj = payload.get("call") or {}
    ext_id = _call_external_id(call_obj)
    agent_id = call_obj.get("agent_id") or call_obj.get("agentId")

    logger.info("Retell webhook", event=event, call_id=ext_id, agent_id=agent_id)

    if event not in ("call_ended", "call_analyzed") or not ext_id:
        return {"ok": True}

    client_id = await _resolve_client_for_agent(str(agent_id) if agent_id else None)

    meta = call_obj.get("metadata")
    if not client_id and meta:
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        if isinstance(meta, dict) and meta.get("client_id"):
            try:
                client_id = UUID(str(meta["client_id"]))
            except ValueError:
                client_id = None

    if not client_id and settings.LANDING_PAGE_CLIENT_ID:
        try:
            client_id = UUID(settings.LANDING_PAGE_CLIENT_ID)
        except ValueError:
            client_id = None

    if not client_id:
        logger.warning("Retell webhook: could not resolve client", agent_id=agent_id)
        return {"ok": True}

    result = await db.execute(select(Call).where(Call.retell_call_id == ext_id))
    call_row = result.scalar_one_or_none()

    transcript_obj = call_obj.get("transcript") or call_obj.get("transcript_object")
    turns: list[dict[str, Any]] = []
    if isinstance(transcript_obj, list):
        turns = transcript_obj
    elif isinstance(transcript_obj, dict) and "transcript" in transcript_obj:
        t = transcript_obj.get("transcript")
        if isinstance(t, list):
            turns = t

    duration_ms = call_obj.get("duration_ms") or call_obj.get("call_duration_ms")
    duration_sec = None
    if duration_ms is not None:
        try:
            duration_sec = int(int(duration_ms) / 1000)
        except (TypeError, ValueError):
            duration_sec = None

    started_ms = call_obj.get("start_timestamp") or call_obj.get("start_time_ms")
    ended_ms = call_obj.get("end_timestamp") or call_obj.get("end_time_ms")

    def _ms_to_dt(ms: Any) -> datetime | None:
        if ms is None:
            return None
        try:
            return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    if not call_row:
        call_row = Call(
            client_id=client_id,
            caller_number=str(call_obj.get("from_number") or call_obj.get("customer_number") or ""),
            direction="inbound" if call_obj.get("call_type") != "web_call" else "inbound",
            channel="voice",
            status="completed",
            retell_call_id=ext_id,
            started_at=_ms_to_dt(started_ms) or _utcnow(),
            ended_at=_ms_to_dt(ended_ms) or _utcnow(),
            duration_seconds=duration_sec,
        )
        db.add(call_row)
        await db.flush()
    else:
        call_row.status = "completed"
        call_row.ended_at = _ms_to_dt(ended_ms) or call_row.ended_at or _utcnow()
        if duration_sec is not None:
            call_row.duration_seconds = duration_sec

    if turns:
        existing = await db.execute(select(Transcript).where(Transcript.call_id == call_row.id))
        tr = existing.scalar_one_or_none()
        normalized: list[dict[str, Any]] = []
        for i, turn in enumerate(turns):
            if not isinstance(turn, dict):
                continue
            role = turn.get("role") or turn.get("speaker") or "agent"
            text = turn.get("content") or turn.get("message") or turn.get("text") or ""
            normalized.append(
                {
                    "speaker": "agent" if role in ("agent", "assistant") else "caller",
                    "text": str(text),
                    "timestamp": float(turn.get("timestamp", i)),
                }
            )
        if tr:
            tr.turns = normalized
        else:
            db.add(
                Transcript(
                    call_id=call_row.id,
                    client_id=client_id,
                    turns=normalized,
                )
            )

    await db.commit()
    return {"ok": True}

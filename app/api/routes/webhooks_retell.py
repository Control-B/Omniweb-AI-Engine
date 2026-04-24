"""Retell webhook handler for AI telephony call lifecycle events."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import select

from app.api.deps import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.models import AgentConfig, Call, PhoneNumber, Transcript
from app.services.post_call_service import PostCallService
from app.services import retell_service

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks/retell", tags=["webhooks"])


@router.post("")
async def retell_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    body = await request.body()
    signature = request.headers.get("X-Retell-Signature", "")
    if not retell_service.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    background_tasks.add_task(_handle_retell_event, payload)
    return {"ok": True}


async def _handle_retell_event(payload: dict) -> None:
    event_type = payload.get("event", "")
    call_data = payload.get("call") or {}
    retell_call_id = call_data.get("call_id")
    agent_id = call_data.get("agent_id")

    logger.info("Retell webhook received: event=%s call_id=%s agent_id=%s", event_type, retell_call_id, agent_id)

    if not retell_call_id or not agent_id:
        logger.warning("Retell webhook missing call_id or agent_id")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AgentConfig).where(AgentConfig.retell_agent_id == agent_id))
        agent_config = result.scalar_one_or_none()
        if not agent_config:
            logger.warning("No agent config found for Retell agent %s", agent_id)
            return

        call = await _upsert_call_from_retell(db, agent_config=agent_config, call_data=call_data, event_type=event_type)
        await db.commit()

        turns = _extract_transcript_turns(call_data.get("transcript_object") or [])
        collected_data = _build_collected_data(call_data)

        if event_type in {"call_ended", "call_analyzed"} and turns and not call.post_call_processed:
            try:
                await PostCallService.process(
                    db=db,
                    call_id=call.id,
                    turns=turns,
                    collected_data=collected_data,
                )
                await db.commit()
            except Exception as exc:
                logger.error("Retell post-call pipeline failed for %s: %s", retell_call_id, exc)

        if event_type == "call_analyzed":
            await _apply_analysis_to_transcript(db, call=call, call_data=call_data)
            await db.commit()


async def _upsert_call_from_retell(db, *, agent_config: AgentConfig, call_data: dict, event_type: str) -> Call:
    retell_call_id = call_data.get("call_id")
    existing = await db.execute(select(Call).where(Call.retell_call_id == retell_call_id))
    call = existing.scalar_one_or_none()

    caller_number = (
        call_data.get("from_number")
        or call_data.get("caller_number")
        or (call_data.get("metadata") or {}).get("caller_number")
        or "unknown"
    )
    called_number = call_data.get("to_number") or (call_data.get("metadata") or {}).get("phone_number")
    phone_number_id = await _lookup_phone_number_id(db, client_id=agent_config.client_id, phone_number=called_number)

    if not call:
        call = Call(
            client_id=agent_config.client_id,
            phone_number_id=phone_number_id,
            caller_number=caller_number,
            direction=call_data.get("direction", "inbound"),
            channel="voice",
            status=_map_status(event_type, call_data),
            provider="retell",
            retell_call_id=retell_call_id,
            started_at=_from_timestamp_ms(call_data.get("start_timestamp")),
            ended_at=_from_timestamp_ms(call_data.get("end_timestamp")),
            duration_seconds=_duration_seconds(call_data),
            recording_url=call_data.get("recording_url"),
        )
        db.add(call)
        await db.flush()
        await db.refresh(call)
    else:
        call.phone_number_id = phone_number_id or call.phone_number_id
        call.caller_number = caller_number or call.caller_number
        call.direction = call_data.get("direction", call.direction)
        call.status = _map_status(event_type, call_data)
        call.provider = "retell"
        call.started_at = _from_timestamp_ms(call_data.get("start_timestamp")) or call.started_at
        call.ended_at = _from_timestamp_ms(call_data.get("end_timestamp")) or call.ended_at
        call.duration_seconds = _duration_seconds(call_data) or call.duration_seconds
        call.recording_url = call_data.get("recording_url") or call.recording_url
        await db.flush()

    return call


async def _lookup_phone_number_id(db, *, client_id, phone_number: str | None):
    if not phone_number:
        return None
    result = await db.execute(
        select(PhoneNumber.id).where(
            PhoneNumber.client_id == client_id,
            PhoneNumber.phone_number == phone_number,
        )
    )
    return result.scalar_one_or_none()


def _extract_transcript_turns(transcript_data: list[dict]) -> list[dict]:
    turns: list[dict] = []
    for entry in transcript_data:
        role = (entry.get("role") or "user").lower()
        speaker = "agent" if role == "agent" else "caller"
        text = (entry.get("content") or "").strip()
        words = entry.get("words") or []
        timestamp = 0.0
        if words:
            first_word = words[0] or {}
            timestamp = float(first_word.get("start") or 0.0)
        if text:
            turns.append({"speaker": speaker, "text": text, "timestamp": timestamp})
    return turns


def _build_collected_data(call_data: dict) -> dict:
    analysis = call_data.get("call_analysis") or {}
    return {
        "call_successful": analysis.get("call_successful"),
        "summary": analysis.get("call_summary"),
        "user_sentiment": analysis.get("user_sentiment"),
        "custom_analysis_data": analysis.get("custom_analysis_data") or {},
        "metadata": call_data.get("metadata") or {},
        "collected_dynamic_variables": call_data.get("collected_dynamic_variables") or {},
    }


async def _apply_analysis_to_transcript(db, *, call: Call, call_data: dict) -> None:
    result = await db.execute(select(Transcript).where(Transcript.call_id == call.id))
    transcript = result.scalar_one_or_none()
    if not transcript:
        transcript = Transcript(call_id=call.id, client_id=call.client_id, turns=_extract_transcript_turns(call_data.get("transcript_object") or []))
        db.add(transcript)
        await db.flush()

    analysis = call_data.get("call_analysis") or {}
    if analysis.get("call_summary"):
        transcript.summary = analysis.get("call_summary")
    if analysis.get("user_sentiment"):
        transcript.sentiment = analysis.get("user_sentiment")
    await db.flush()


def _map_status(event_type: str, call_data: dict) -> str:
    if event_type == "call_started":
        return "ongoing"
    if event_type in {"call_ended", "call_analyzed"}:
        call_status = (call_data.get("call_status") or "").lower()
        if call_status == "error":
            return "failed"
        return "completed"
    return (call_data.get("call_status") or "queued").lower()


def _duration_seconds(call_data: dict) -> int | None:
    duration_ms = call_data.get("duration_ms")
    if duration_ms is None:
        return None
    try:
        return int(round(float(duration_ms) / 1000))
    except (TypeError, ValueError):
        return None


def _from_timestamp_ms(value: int | float | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None

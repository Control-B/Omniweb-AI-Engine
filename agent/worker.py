"""Omniweb LiveKit Agent Worker.

Self-hosted voice agent that receives per-tenant system prompts via
dispatch metadata. Uses LiveKit Inference for the full STT → LLM → TTS
pipeline (Deepgram Nova-3 → GPT-4.1 mini → Cartesia Sonic-3) — no
extra API keys needed beyond the LiveKit Cloud project.

Architecture:
  1. Frontend calls ``POST /api/livekit/token`` on the FastAPI engine.
  2. Engine composes a system prompt (via prompt_engine) for the tenant,
     creates a dispatch with the prompt as JSON metadata, and returns
     a token to the frontend.
  3. LiveKit Cloud routes the dispatch to THIS worker.
  4. Worker reads ``ctx.job.metadata``, extracts system_prompt + first_message
     + language, creates an ``AgentSession`` with dynamic instructions, and
     starts talking.

Deployment:
  Run as a separate process alongside (or instead of) the FastAPI app:
    python agent/worker.py dev      # local development
    python agent/worker.py start    # production
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

# Load .env from project root (needed when running standalone: python agent/worker.py)
from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, TurnHandlingOptions, llm
from livekit.agents.inference.tts import TTS as InferenceTTS
from livekit.agents.llm.tool_context import StopResponse
from livekit.plugins import silero

from app.core.config import get_settings

logger = logging.getLogger("omniweb-agent")
logger.setLevel(logging.INFO)
settings = get_settings()

# ── Default prompt (used when no metadata is provided) ────────────────────────

DEFAULT_INSTRUCTIONS = """You are a helpful AI voice assistant powered by Omniweb.
You help website visitors learn about Omniweb's AI voice agent platform.
Omniweb lets businesses deploy intelligent AI voice and text agents on their
websites to capture leads, book appointments, and provide 24/7 customer service.

Be conversational, warm, and concise. Use 1-3 sentences per response.
Lead with value, not questions. Sound like a top-performing sales rep.
"""

DEFAULT_FIRST_MESSAGE = (
    "Hey! I'm the Omniweb AI assistant. "
    "I help businesses turn website visitors into customers using intelligent "
    "voice and text agents. What can I help you with today?"
)
BACKGROUND_NOISE_HINTS = (
    "tv",
    "television",
    "radio",
    "podcast",
    "youtube",
    "movie",
    "commercial",
    "episode",
    "watching",
    "luke",
    "sensor",
    "lithium",
)

DIRECTED_SPEECH_HINTS = (
    "omniweb",
    "ava",
    "can you",
    "could you",
    "would you",
    "will you",
    "help me",
    "tell me",
    "show me",
    "what",
    "how",
    "why",
    "when",
    "where",
    "pricing",
    "price",
    "cost",
    "plan",
    "demo",
    "trial",
    "business",
    "website",
    "agent",
    "voice",
    "text",
    "ai",
    "book",
    "appointment",
    "lead",
    "crm",
    "integrat",
)

AMBIENT_SPEECH_HINTS = BACKGROUND_NOISE_HINTS + (
    "mom",
    "class",
    "post",
    "proud",
    "friend",
    "show",
    "design",
    "school",
    "wrist",
)

# Map language codes → Deepgram STT model variants for best accuracy.
# All use Nova-3; the suffix tells Deepgram which language to optimise for.
DEEPGRAM_LANG_MAP: dict[str, str] = {
    "en": "deepgram/nova-3",            # English (default, auto-detect)
    "es": "deepgram/nova-3:es",
    "fr": "deepgram/nova-3:fr",
    "de": "deepgram/nova-3:de",
    "pt": "deepgram/nova-3:pt",
    "it": "deepgram/nova-3:it",
    "nl": "deepgram/nova-3:nl",
    "ja": "deepgram/nova-3:ja",
    "ko": "deepgram/nova-3:ko",
    "zh": "deepgram/nova-3:zh",
    "hi": "deepgram/nova-3:hi",
    "ru": "deepgram/nova-3:ru",
    "ar": "deepgram/nova-3:ar",
    "tr": "deepgram/nova-3:tr",
    "pl": "deepgram/nova-3:pl",
    "uk": "deepgram/nova-3:uk",
    "sv": "deepgram/nova-3:sv",
    "da": "deepgram/nova-3:da",
    "no": "deepgram/nova-3:no",
    "fi": "deepgram/nova-3:fi",
    "el": "deepgram/nova-3:el",
    "cs": "deepgram/nova-3:cs",
    "ro": "deepgram/nova-3:ro",
    "hu": "deepgram/nova-3:hu",
    "th": "deepgram/nova-3:th",
    "id": "deepgram/nova-3:id",
    "ms": "deepgram/nova-3:ms",
    "vi": "deepgram/nova-3:vi",
    "bg": "deepgram/nova-3:bg",
    "ta": "deepgram/nova-3:ta",
}

AUTO_GREET_ON_CONNECT = os.getenv("LIVEKIT_AUTO_GREET", "true").lower() == "true"


def _resolve_elevenlabs_voice_id(language: str) -> str | None:
    voice_id = getattr(settings, f"ELEVENLABS_VOICE_ID_{language.upper()}", None)
    return voice_id or settings.ELEVENLABS_DEFAULT_VOICE_ID or None


def _build_tts(language: str) -> InferenceTTS:
    extra_kwargs: dict[str, object] = {
        "stability": 0.35,
        "similarity_boost": 0.8,
        "style": 0.28,
        "speed": 1.0,
        "use_speaker_boost": True,
        "auto_mode": True,
        "inactivity_timeout": 20,
    }
    if language:
        extra_kwargs["language_code"] = language

    tts_kwargs: dict[str, object] = {
        "model": "elevenlabs/eleven_flash_v2_5",
        "language": language,
        "extra_kwargs": extra_kwargs,
        "fallback": [
            {
                "model": "cartesia/sonic-3",
                "voice": "",
                "extra_kwargs": {
                    "emotion": "positivity",
                    "speed": "normal",
                },
            }
        ],
    }

    voice_id = _resolve_elevenlabs_voice_id(language)
    if voice_id:
        tts_kwargs["voice"] = voice_id

    return InferenceTTS(**tts_kwargs)


# ── Dynamic Agent that accepts runtime instructions ───────────────────────────


class OmniwebAgent(Agent):
    """Voice agent whose instructions are set dynamically per session."""

    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        transcript = (new_message.text_content or "").strip()
        if not transcript:
            raise StopResponse()

        if _should_ignore_transcript(transcript):
            logger.info("Ignoring likely ambient transcript: %s", transcript)
            raise StopResponse()


def _should_ignore_transcript(transcript: str) -> bool:
    lowered = transcript.strip().lower()
    if not lowered:
        return True

    words = lowered.split()

    if len(words) <= 2 and lowered in {"hello", "hello?", "hi", "hey", "okay", "ok"}:
        return True

    if any(hint in lowered for hint in DIRECTED_SPEECH_HINTS):
        return False

    if "?" in lowered and len(words) >= 3:
        return False

    if any(hint in lowered for hint in AMBIENT_SPEECH_HINTS):
        return True

    if len(words) >= 8:
        return True

    return False


def _extract_text_user_message(packet: rtc.DataPacket) -> str | None:
    raw_payload = packet.data.decode("utf-8", errors="ignore").strip()
    if not raw_payload:
        return None

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return raw_payload

    message_type = payload.get("type")
    if message_type and message_type != "user_message":
        return None

    text = str(payload.get("text") or "").strip()
    return text or None


async def _publish_text_response(room: rtc.Room, text: str) -> None:
    payload = json.dumps({"type": "response", "text": text}, ensure_ascii=False)
    await room.local_participant.publish_data(payload, reliable=True)


# ── Agent Server & Entrypoint ─────────────────────────────────────────────────

server = AgentServer()


@server.rtc_session(agent_name="BanjahMac")
async def omniweb_entrypoint(ctx: agents.JobContext):
    """Entrypoint called by LiveKit for each dispatched session.

    Reads the system prompt, first message, and language from dispatch
    metadata, then creates an AgentSession with LiveKit Inference providers.
    """

    # ── Parse dispatch metadata ──────────────────────────────────────────
    system_prompt = DEFAULT_INSTRUCTIONS
    first_message = DEFAULT_FIRST_MESSAGE
    language = "en"

    if ctx.job.metadata:
        try:
            meta = json.loads(ctx.job.metadata)
            system_prompt = meta.get("system_prompt", DEFAULT_INSTRUCTIONS)
            first_message = meta.get("first_message", DEFAULT_FIRST_MESSAGE)
            language = meta.get("language", "en")
            logger.info(
                "Loaded dispatch metadata (prompt_len=%d, greeting_len=%d, lang=%s)",
                len(system_prompt),
                len(first_message),
                language,
            )
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse dispatch metadata: %s", exc)

    # ── Select STT model based on language ───────────────────────────────
    stt_model = DEEPGRAM_LANG_MAP.get(language, "deepgram/nova-3:multi")

    # ── Create agent session ─────────────────────────────────────────────
    # LiveKit Inference model strings — no API keys needed, billed through
    # the LiveKit Cloud project.
    session = AgentSession(
        stt=stt_model,
        llm="openai/gpt-4.1-mini",
        tts=_build_tts(language),
        vad=silero.VAD.load(
            min_silence_duration=0.7,   # reduce awkward wait before a reply starts
            min_speech_duration=0.4,    # ignore short bursts and clipped background phrases
            activation_threshold=0.72,  # require stronger voice confidence before triggering
        ),
        turn_handling=TurnHandlingOptions(
            endpointing={
                "mode": "dynamic",
                "min_delay": 0.35,
                "max_delay": 1.2,
            },
            interruption={
                "enabled": True,
                "mode": "vad",
                "min_duration": 0.85,
                "min_words": 2,
                "resume_false_interruption": True,
                "false_interruption_timeout": 1.2,
            },
        ),
    )

    # ── Anti-noise & conciseness guardrails ──────────────────────────
    system_prompt += (
        "\n\n## Voice Conversation Rules\n"
        "- Keep every response to 1-3 SHORT sentences. You are in a real-time voice call — brevity is critical.\n"
        "- NEVER repeat yourself or restate what the user said unless asked to.\n"
        "- Sound warm, fluid, and human — never stiff, monotone, translated, or robotic.\n"
        "- Use natural pacing and idiomatic phrasing in the user's language.\n"
                    "- Speak in short, interruptible chunks. Do not deliver long monologues or dense paragraphs out loud.\n"
                    "- Sometimes use natural spoken connectors like 'so', 'but', 'and', 'right', or 'anyway' when they genuinely fit.\n"
                    "- You may use a light filler like 'um', 'uh', 'yeah', or 'got it' OCCASIONALLY to sound natural, but never in every reply and never more than once in a short reply.\n"
                    "- You may occasionally make one brief self-repair if it improves clarity, such as 'what I mean is...' or 'actually, the simpler way to put it is...' Do this sparingly.\n"
                    "- Use brief pauses between ideas and slow down slightly for important details like names, times, prices, dates, links, and next steps.\n"
                    "- If you need a moment to think, check something, or wait on a tool, briefly narrate that you are checking instead of going fully silent.\n"
                    "- If there is a short hold or delay, keep the user oriented with one calm status line, then return with the answer. Do not over-narrate.\n"
                    "- Default to calm, grounded delivery. If emotion is needed, make it subtle and reassuring rather than theatrical or over-acted.\n"
                    "- In non-English languages, use native conversational transitions and fillers only when they sound natural in that language. Do not inject English discourse markers into another language.\n"
        "- Open the session with one concise welcome statement, then wait silently for the user.\n"
        "- Stay passive until the user clearly speaks to you. Do not take initiative unless directly addressed.\n"
        "- Brief greetings like 'hi', 'hello', or 'hey' count as directed speech and should receive a normal response.\n"
        "- If speech sounds like background chatter, TV, radio, or a conversation not directed at you, IGNORE it and do not respond.\n"
        "- If you only hear fragments, accidental noise, or an incomplete thought, stay silent instead of guessing.\n"
        "- Only respond after a clear, complete sentence that sounds directed at you.\n"
        "- If the user hangs up, disconnects, or the session ends, do nothing further. Never restart or continue on your own.\n"
        "- If the user is clearly addressing you but the utterance is still unclear, ask one short clarifying question.\n"
    )

    system_prompt += (
        "\n## Ignore These As Background Noise\n"
        + ", ".join(BACKGROUND_NOISE_HINTS)
        + ".\nTreat these as likely ambient speech if they appear out of context."
    )
    # Add language instruction so the LLM responds in the correct language
    if language != "en":
        system_prompt += (
            f"\n## Language\nYou MUST respond in the language with code '{language}'. "
            "The user chose this language. Always respond in this language unless they explicitly switch. "
            "Use native, idiomatic phrasing in that language — not literal English translation."
        )

    await session.start(
        room=ctx.room,
        agent=OmniwebAgent(instructions=system_prompt),
    )

    pending_text_replies = 0

    async def _handle_text_message(packet: rtc.DataPacket) -> None:
        nonlocal pending_text_replies

        text = _extract_text_user_message(packet)
        if not text:
            return

        logger.info("Received text chat message (len=%d)", len(text))
        pending_text_replies += 1

        try:
            session.generate_reply(
                user_input=text,
                input_modality="text",
                allow_interruptions=False,
            )
        except Exception:
            pending_text_replies = max(0, pending_text_replies - 1)
            logger.exception("Failed to generate text reply")
            await _publish_text_response(
                ctx.room,
                "Sorry — I’m having trouble replying right now. Please try again.",
            )

    @ctx.room.on("data_received")
    def _on_data_received(packet: rtc.DataPacket) -> None:
        asyncio.create_task(_handle_text_message(packet))

    @session.on("conversation_item_added")
    def _on_conversation_item_added(event) -> None:
        nonlocal pending_text_replies

        item = event.item
        if getattr(item, "role", None) != "assistant":
            return

        text = (item.text_content or "").strip()
        if not text or pending_text_replies <= 0:
            return

        pending_text_replies -= 1
        asyncio.create_task(_publish_text_response(ctx.room, text))

    # ── Optional first message (disabled by default to avoid over-eager starts)
    if AUTO_GREET_ON_CONNECT:
        if language != "en":
            greeting_instruction = (
                f"Greet the user now in the language with code '{language}'. "
                f"Translate and adapt this greeting naturally (do NOT speak English): "
                f"{first_message}"
            )
            await session.generate_reply(instructions=greeting_instruction)
        else:
            await session.generate_reply(instructions=first_message)


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    agents.cli.run_app(server)

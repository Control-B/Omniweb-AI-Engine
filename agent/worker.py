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

import json
import logging
import os
from pathlib import Path

# Load .env from project root (needed when running standalone: python agent/worker.py)
from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, room_io, TurnHandlingOptions
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("omniweb-agent")
logger.setLevel(logging.INFO)

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


# ── Dynamic Agent that accepts runtime instructions ───────────────────────────


class OmniwebAgent(Agent):
    """Voice agent whose instructions are set dynamically per session."""

    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)


# ── Agent Server & Entrypoint ─────────────────────────────────────────────────

server = AgentServer()


@server.rtc_session(agent_name="omniweb-agent")
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
        tts="cartesia/sonic",
        vad=silero.VAD.load(
            min_silence_duration=0.6,   # require 600ms silence before end-of-turn (reduces background noise triggers)
            min_speech_duration=0.15,   # ignore very short bursts (< 150ms) — likely noise
            activation_threshold=0.6,   # higher confidence needed to count as speech (default 0.5)
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),  # smarter turn detection — reduces false triggers
        ),
    )

    # Add language instruction to the system prompt so the LLM responds
    # in the correct language
    if language != "en":
        system_prompt += f"\n\n## Language\nRespond in the language with code '{language}'. The user chose this language. Always respond in this language unless they switch."

    await session.start(
        room=ctx.room,
        agent=OmniwebAgent(instructions=system_prompt),
    )

    # ── Send the first message (greeting) ────────────────────────────────
    await session.generate_reply(instructions=first_message)


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    agents.cli.run_app(server)

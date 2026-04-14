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
  4. Worker reads ``ctx.job.metadata``, extracts system_prompt + first_message,
     creates an ``AgentSession`` with dynamic instructions, and starts talking.

Deployment:
  Run as a separate process alongside (or instead of) the FastAPI app:
    python agent/worker.py dev      # local development
    python agent/worker.py start    # production
"""
from __future__ import annotations

import json
import logging

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import silero

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

    Reads the system prompt and first message from dispatch metadata,
    then creates an AgentSession with LiveKit Inference providers.
    """

    # ── Parse dispatch metadata ──────────────────────────────────────────
    system_prompt = DEFAULT_INSTRUCTIONS
    first_message = DEFAULT_FIRST_MESSAGE

    if ctx.job.metadata:
        try:
            meta = json.loads(ctx.job.metadata)
            system_prompt = meta.get("system_prompt", DEFAULT_INSTRUCTIONS)
            first_message = meta.get("first_message", DEFAULT_FIRST_MESSAGE)
            logger.info(
                "Loaded prompt from dispatch metadata (len=%d, greeting_len=%d)",
                len(system_prompt),
                len(first_message),
            )
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse dispatch metadata: %s", exc)

    # ── Create agent session ─────────────────────────────────────────────
    # LiveKit Inference model strings — no API keys needed, billed through
    # the LiveKit Cloud project.
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic",
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=OmniwebAgent(instructions=system_prompt),
    )

    # ── Send the first message (greeting) ────────────────────────────────
    await session.generate_reply(instructions=first_message)


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    agents.cli.run_app(server)

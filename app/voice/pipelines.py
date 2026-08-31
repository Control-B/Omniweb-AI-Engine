"""Pluggable Realtime Voice Pipelines for LiveKit Interaction Plane.

Supports:
- Pipeline A: Deepgram Nova-3 STT ➔ LangGraph / Gemini ➔ Cartesia / ElevenLabs TTS
- Pipeline B: Gemini 2.0 Multimodal Live Speech (Direct Audio-to-Audio)
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class VoicePipelineType(str, Enum):
    PIPELINE_A_CASCADED = "cascaded_stt_llm_tts"      # Deepgram + Gemini + Cartesia/ElevenLabs
    PIPELINE_B_MULTIMODAL = "gemini_multimodal_live"    # Gemini 2.0 Multimodal Live Audio


class VoicePipelineConfig(BaseModel):
    pipeline_type: VoicePipelineType = VoicePipelineType.PIPELINE_A_CASCADED
    stt_model: str = "nova-3"
    stt_language: str = "en"
    llm_model: str = "gemini-2.0-flash"
    tts_voice: str = "aura-asteria-en"
    allow_interruptions: bool = True
    vad_threshold: float = 0.5
    silence_timeout_ms: int = 400


class VoicePipelineManager:
    """Manages voice pipeline selection and per-tenant voice configurations."""

    @staticmethod
    def get_pipeline_config(tenant_id: str, channel_type: str = "phone_inbound") -> VoicePipelineConfig:
        """Resolve voice pipeline configuration for a given tenant."""
        # Pipeline B can be enabled if gemini_configured and feature flag active
        if settings.ENABLE_GEMINI_LIVE and settings.gemini_configured:
            return VoicePipelineConfig(
                pipeline_type=VoicePipelineType.PIPELINE_B_MULTIMODAL,
                llm_model=settings.GEMINI_LIVE_SPEECH_MODEL,
                allow_interruptions=True,
            )
        return VoicePipelineConfig(
            pipeline_type=VoicePipelineType.PIPELINE_A_CASCADED,
            stt_model=settings.DEEPGRAM_STT_MODEL,
            tts_voice=settings.DEEPGRAM_TTS_VOICE,
            llm_model=settings.DEFAULT_CONVERSATION_MODEL,
            allow_interruptions=True,
        )

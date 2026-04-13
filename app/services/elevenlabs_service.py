"""ElevenLabs Conversational AI service — the voice + text + KB engine.

Architecture (ElevenLabs-native):

  Caller dials Twilio number
      → Twilio number is imported into ElevenLabs
      → ElevenLabs agent picks up, handles full conversation
      → STT (ElevenLabs) → LLM (GPT-4o / Claude) → TTS (ElevenLabs)
      → Conversation ends → ElevenLabs fires webhook to our FastAPI
      → FastAPI runs post-call pipeline (transcript, lead, SMS, CRM)

  Text Chat (widget / API):
      → User connects via embeddable widget or WebSocket
      → Same ElevenLabs agent, same knowledge base
      → Conversation logged identically to voice calls

ElevenLabs hosts:
  ✅ Agent runtime (no worker process needed)
  ✅ Voice pipeline (STT + TTS + LLM orchestration)
  ✅ Text chat via widget / WebSocket
  ✅ Knowledge Base (RAG)
  ✅ Phone number management (imported from Twilio)
  ✅ Conversation history + transcripts
  ✅ WhatsApp (bonus)

FastAPI role:
  - Multi-tenant config management (one ElevenLabs agent per client)
  - Receive ElevenLabs post-conversation webhooks
  - CRM, SMS follow-ups, lead extraction
  - Dashboard API
  - Billing (Stripe)
"""
import json
from io import BytesIO
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

BASE_URL = "https://api.elevenlabs.io/v1"
CONVAI_URL = f"{BASE_URL}/convai"
TTS_URL = f"{BASE_URL}/text-to-speech"

SUPPORTED_LANGUAGE_OPTIONS: list[dict[str, Any]] = [
    {"code": "ar", "label": "Arabic", "rtl": True},
    {"code": "de", "label": "German"},
    {"code": "en", "label": "English"},
    {"code": "es", "label": "Spanish"},
    {"code": "fr", "label": "French"},
    {"code": "hi", "label": "Hindi"},
    {"code": "it", "label": "Italian"},
    {"code": "ja", "label": "Japanese"},
    {"code": "ko", "label": "Korean"},
    {"code": "nl", "label": "Dutch"},
    {"code": "pl", "label": "Polish"},
    {"code": "pt", "label": "Portuguese"},
    {"code": "ru", "label": "Russian"},
    {"code": "tr", "label": "Turkish"},
    {"code": "uk", "label": "Ukrainian"},
    {"code": "zh", "label": "Chinese"},
]


def _normalize_language_code(language: str | None) -> str:
    if not language:
        return settings.ELEVENLABS_DEFAULT_LANGUAGE
    return language.strip().lower().replace("_", "-").split("-", 1)[0]


def _voice_id_for_language(language: str | None) -> str | None:
    normalized = _normalize_language_code(language)
    env_key = f"ELEVENLABS_VOICE_ID_{normalized.upper()}"
    configured_voice = getattr(settings, env_key, None)
    return configured_voice or None


def resolve_voice_id(*, language: str | None = None, voice_id: str | None = None) -> str:
    return (
        voice_id
        or _voice_id_for_language(language)
        or settings.ELEVENLABS_DEFAULT_VOICE_ID
    )


def get_language_options() -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    default_language = _normalize_language_code(settings.ELEVENLABS_DEFAULT_LANGUAGE)

    for item in SUPPORTED_LANGUAGE_OPTIONS:
        code = item["code"]
        resolved_voice_id = resolve_voice_id(language=code)
        explicitly_configured = bool(_voice_id_for_language(code))
        options.append(
            {
                **item,
                "voice_id": resolved_voice_id,
                "configured": explicitly_configured or code == default_language,
                "default": code == default_language,
            }
        )

    return options


# ── Default first messages per language (used when creating agents) ─────────
DEFAULT_FIRST_MESSAGES: dict[str, str] = {
    "ar": "مرحبًا! كيف يمكنني مساعدتك اليوم؟",
    "de": "Hallo! Wie kann ich Ihnen heute helfen?",
    "en": "Hi, I'd love to help you today, so tell me the problem you're trying to solve, and I'll understand your needs, recommend the right solution, and answer your questions so you can move forward faster by text or voice. Talk to me.",
    "es": "¡Hola! ¿En qué puedo ayudarte hoy?",
    "fr": "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
    "hi": "नमस्ते! आज मैं आपकी कैसे मदद कर सकता हूँ?",
    "it": "Ciao! Come posso aiutarti oggi?",
    "ja": "こんにちは！本日はどのようなご用件でしょうか？",
    "ko": "안녕하세요! 오늘 어떻게 도와드릴까요?",
    "nl": "Hallo! Hoe kan ik u vandaag helpen?",
    "pl": "Cześć! W czym mogę Ci dziś pomóc?",
    "pt": "Olá! Como posso ajudá-lo hoje?",
    "ru": "Здравствуйте! Чем могу помочь сегодня?",
    "tr": "Merhaba! Bugün size nasıl yardımcı olabilirim?",
    "uk": "Привіт! Чим можу допомогти сьогодні?",
    "zh": "您好！今天有什么可以帮您的吗？",
}


def build_language_presets(
    *,
    languages: list[str],
    business_name: str = "",
    greeting_template: str | None = None,
    voice_id: str | None = None,
) -> dict[str, Any]:
    """Build the ElevenLabs `language_presets` dict for a set of languages.

    Each preset overrides the agent's first_message and language code.
    Optionally sets a per-language voice.

    Args:
        languages: List of ISO-639-1 codes to enable (e.g. ['en','es','fr']).
        business_name: Substituted into greetings if {business} placeholder exists.
        greeting_template: Optional template per language. If None, uses defaults.
        voice_id: Optional voice to set for all presets (None = use agent default).
    """
    presets: dict[str, Any] = {}
    for lang in languages:
        code = lang.strip().lower()
        if code == "en":  # English is the base, not a preset
            continue

        first_message = DEFAULT_FIRST_MESSAGES.get(code, DEFAULT_FIRST_MESSAGES["en"])
        if business_name:
            # Allow templates like "Thanks for calling {business}!"
            first_message = first_message.replace("{business}", business_name)

        agent_overrides: dict[str, Any] = {
            "first_message": first_message,
            "language": code,
        }

        tts_overrides: dict[str, Any] = {}
        lang_voice = _voice_id_for_language(code) or voice_id
        if lang_voice:
            tts_overrides["voice_id"] = lang_voice

        overrides: dict[str, Any] = {"agent": agent_overrides}
        if tts_overrides:
            overrides["tts"] = tts_overrides

        presets[code] = {"overrides": overrides}

    return presets


def _headers() -> dict[str, str]:
    """Default headers for ElevenLabs API."""
    return {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30, headers=_headers())


def _default_overrides() -> dict[str, Any]:
    """Return the overrides config for voice-first behaviour with text support.

    - ``conversation.text_only`` is overridable (True) — the SDK can pass
      ``textOnly: true`` to start a text-only session, OR leave it False
      for a voice session.  This does NOT force text-only by default.
    - ``agent.first_message`` is not overridable (False) — the first message
      always comes from the agent config, spoken aloud on voice connect.
    - ``agent.language`` is overridable (True) — the SDK can switch languages.
    """
    return {
        "conversation_config_override": {
            "conversation": {
                "text_only": True,
            },
            "agent": {
                "first_message": False,
                "language": True,
            },
        },
    }


def _default_widget_settings(*, language_selector: bool) -> dict[str, Any]:
    """Return the widget config for all agents.

    Key behavior:
    - ``expandable="never"`` → disables the expandable sheet/panel entirely,
      so the widget never shows the "Choose how to chat" screen.
    - ``text_only=False`` → voice is the default start mode.
    - ``supports_text_only=True`` → allows text-only sessions via the SDK.
    - ``text_input_enabled=True`` → allows text input during sessions.
    - ``transcript_enabled=False`` → no transcript panel (keeps widget compact).
    - ``conversation_mode_toggle_enabled=False`` → removes the text/voice
      toggle in the ElevenLabs widget header (we handle mode toggle in our own UI).
    - The agent's ``first_message`` is spoken aloud by TTS on voice connect,
      never shown as a text bubble (text-only prepend is disabled in overrides).
    """
    return {
        "variant": "compact",
        "expandable": "never",
        "shareable_page_enabled": True,
        "text_only": False,
        "text_input_enabled": True,
        "supports_text_only": True,
        "transcript_enabled": False,
        "feedback_mode": "during",
        "language_selector": language_selector,
        "conversation_mode_toggle_enabled": False,
        "text_contents": {
            "start_call": "Talk to me",
        },
    }


async def synthesize_speech(
    *,
    text: str,
    language: str | None = None,
    voice_id: str | None = None,
    model_id: str = "eleven_turbo_v2_5",
) -> bytes:
    """Synthesize speech with ElevenLabs and return MP3 bytes."""
    if not settings.ELEVENLABS_API_KEY:
        raise RuntimeError("ElevenLabs is not configured")

    selected_voice_id = resolve_voice_id(language=language, voice_id=voice_id)
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45, headers=headers) as http:
        resp = await http.post(f"{TTS_URL}/{selected_voice_id}", json=payload)
        resp.raise_for_status()
        return resp.content


# ══════════════════════════════════════════════════════════════════════════════
# AGENTS
# ══════════════════════════════════════════════════════════════════════════════


async def create_agent(
    *,
    name: str,
    first_message: str,
    system_prompt: str,
    voice_id: str = "EXAVITQu4vr4xnSDxMaL",
    llm_model: str = "gpt-4o",
    temperature: float = 0.7,
    language: str = "en",
    max_duration_seconds: int = 1800,
    voice_stability: float = 0.5,
    voice_similarity_boost: float = 0.8,
    knowledge_base_ids: list[str] | None = None,
    supported_languages: list[str] | None = None,
    language_presets_override: dict[str, Any] | None = None,
    business_name: str = "",
) -> dict:
    """Create an ElevenLabs Conversational AI agent.

    Returns {"agent_id": "..."}.
    """
    # Build language presets for multilingual support
    if language_presets_override is not None:
        lang_presets = language_presets_override
    elif supported_languages:
        lang_presets = build_language_presets(
            languages=supported_languages,
            business_name=business_name,
            voice_id=voice_id,
        )
    else:
        # Default: enable all supported languages
        lang_presets = build_language_presets(
            languages=[item["code"] for item in SUPPORTED_LANGUAGE_OPTIONS],
            business_name=business_name,
            voice_id=voice_id,
        )

    agent_config: dict[str, Any] = {
        "agent": {
            "first_message": first_message,
            "language": language,
            "prompt": {
                "prompt": system_prompt,
            },
        },
        "tts": {
            "voice_id": voice_id,
            "stability": voice_stability,
            "similarity_boost": voice_similarity_boost,
        },
        "conversation": {
            "max_duration_seconds": max_duration_seconds,
        },
    }

    # Add language presets if any non-English languages are configured
    if lang_presets:
        agent_config["language_presets"] = lang_presets

    # Add knowledge base if provided
    platform_settings: dict[str, Any] = {
        "widget": _default_widget_settings(language_selector=bool(lang_presets)),
        "overrides": _default_overrides(),
    }
    if knowledge_base_ids:
        agent_config["agent"]["knowledge_base"] = [
            {"id": kb_id, "usage": "auto"} for kb_id in knowledge_base_ids
        ]

    payload: dict[str, Any] = {
        "name": name,
        "conversation_config": agent_config,
        "platform_settings": platform_settings,
    }

    if not settings.ELEVENLABS_API_KEY:
        logger.info(f"[STUB] Would create ElevenLabs agent: {name}")
        return {"agent_id": f"agent_stub_{name[:20]}"}

    async with _client() as http:
        resp = await http.post(f"{CONVAI_URL}/agents/create", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Created ElevenLabs agent '{name}': {data['agent_id']}")
        return data


async def update_agent(
    agent_id: str,
    *,
    name: str | None = None,
    first_message: str | None = None,
    system_prompt: str | None = None,
    voice_id: str | None = None,
    voice_stability: float | None = None,
    voice_similarity_boost: float | None = None,
    language: str | None = None,
    max_duration_seconds: int | None = None,
    knowledge_base_ids: list[str] | None = None,
    supported_languages: list[str] | None = None,
    language_presets_override: dict[str, Any] | None = None,
    business_name: str = "",
) -> dict:
    """Update an ElevenLabs agent's configuration (PATCH)."""
    payload: dict[str, Any] = {}

    if name:
        payload["name"] = name

    conversation_config: dict[str, Any] = {}

    # Agent sub-config
    agent_sub: dict[str, Any] = {}
    if first_message is not None:
        agent_sub["first_message"] = first_message
    if system_prompt is not None:
        agent_sub["prompt"] = {"prompt": system_prompt}
    if language is not None:
        agent_sub["language"] = language
    if knowledge_base_ids is not None:
        agent_sub["knowledge_base"] = [
            {"id": kb_id, "usage": "auto"} for kb_id in knowledge_base_ids
        ]
    if agent_sub:
        conversation_config["agent"] = agent_sub

    # TTS sub-config
    tts_sub: dict[str, Any] = {}
    if voice_id is not None:
        tts_sub["voice_id"] = voice_id
    if voice_stability is not None:
        tts_sub["stability"] = voice_stability
    if voice_similarity_boost is not None:
        tts_sub["similarity_boost"] = voice_similarity_boost
    if tts_sub:
        conversation_config["tts"] = tts_sub

    # Conversation sub-config
    if max_duration_seconds is not None:
        conversation_config["conversation"] = {
            "max_duration_seconds": max_duration_seconds
        }

    # Language presets
    widget_settings = _default_widget_settings(
        language_selector=bool(language_presets_override) if language_presets_override is not None else bool(supported_languages)
    )

    if language_presets_override is not None:
        conversation_config["language_presets"] = language_presets_override
        payload.setdefault("platform_settings", {})["widget"] = widget_settings
    elif supported_languages is not None:
        lang_presets = build_language_presets(
            languages=supported_languages,
            business_name=business_name,
            voice_id=voice_id,
        )
        conversation_config["language_presets"] = lang_presets
        payload.setdefault("platform_settings", {})["widget"] = _default_widget_settings(
            language_selector=bool(lang_presets)
        )

    if "platform_settings" not in payload:
        payload["platform_settings"] = {"widget": widget_settings}

    # Always send overrides to lock down voice-first behaviour
    payload.setdefault("platform_settings", {})["overrides"] = _default_overrides()

    if conversation_config:
        payload["conversation_config"] = conversation_config

    if not payload:
        return {"agent_id": agent_id}

    if not settings.ELEVENLABS_API_KEY:
        logger.info(f"[STUB] Would update ElevenLabs agent: {agent_id}")
        return {"agent_id": agent_id}

    async with _client() as http:
        resp = await http.patch(f"{CONVAI_URL}/agents/{agent_id}", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Updated ElevenLabs agent {agent_id}")
        return data


async def get_agent(agent_id: str) -> dict:
    """Get full agent configuration."""
    if not settings.ELEVENLABS_API_KEY:
        return {"agent_id": agent_id, "name": "stub"}

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/agents/{agent_id}")
        resp.raise_for_status()
        return resp.json()


async def delete_agent(agent_id: str) -> bool:
    """Delete an ElevenLabs agent."""
    if not settings.ELEVENLABS_API_KEY:
        return True

    async with _client() as http:
        resp = await http.delete(f"{CONVAI_URL}/agents/{agent_id}")
        if resp.status_code in (200, 204, 404):
            logger.info(f"Deleted ElevenLabs agent {agent_id}")
            return True
        resp.raise_for_status()
        return False


async def list_agents() -> list[dict]:
    """List all agents in the ElevenLabs account."""
    if not settings.ELEVENLABS_API_KEY:
        return []

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/agents")
        resp.raise_for_status()
        data = resp.json()
        return data.get("agents", [])


# ══════════════════════════════════════════════════════════════════════════════
# PHONE NUMBERS
# ══════════════════════════════════════════════════════════════════════════════


async def import_twilio_phone_number(
    *,
    phone_number: str,
    label: str,
    twilio_account_sid: str,
    twilio_auth_token: str,
    agent_id: str | None = None,
) -> dict:
    """Import a Twilio phone number into ElevenLabs.

    After import, ElevenLabs configures the Twilio number to route calls
    to the specified agent.

    Returns {"phone_number_id": "..."}.
    """
    payload: dict[str, Any] = {
        "phone_number": phone_number,
        "label": label,
        "sid": twilio_account_sid,
        "token": twilio_auth_token,
    }

    if not settings.ELEVENLABS_API_KEY:
        import uuid
        logger.info(f"[STUB] Would import Twilio number {phone_number} into ElevenLabs")
        return {"phone_number_id": f"phone_stub_{uuid.uuid4().hex[:12]}"}

    async with _client() as http:
        resp = await http.post(f"{CONVAI_URL}/phone-numbers", json=payload)
        resp.raise_for_status()
        data = resp.json()
        phone_number_id = data["phone_number_id"]
        logger.info(f"Imported Twilio number {phone_number} → ElevenLabs: {phone_number_id}")

        # Assign to agent if specified
        if agent_id:
            await assign_phone_to_agent(phone_number_id, agent_id)

        return data


async def assign_phone_to_agent(phone_number_id: str, agent_id: str) -> dict:
    """Assign a phone number to a specific ElevenLabs agent."""
    if not settings.ELEVENLABS_API_KEY:
        return {"phone_number_id": phone_number_id}

    async with _client() as http:
        resp = await http.patch(
            f"{CONVAI_URL}/phone-numbers/{phone_number_id}",
            json={"agent_id": agent_id},
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Assigned phone {phone_number_id} to agent {agent_id}")
        return data


async def list_phone_numbers() -> list[dict]:
    """List all phone numbers in the ElevenLabs account."""
    if not settings.ELEVENLABS_API_KEY:
        return []

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/phone-numbers")
        resp.raise_for_status()
        return resp.json()


async def delete_phone_number(phone_number_id: str) -> bool:
    """Remove a phone number from ElevenLabs (does NOT release the Twilio number)."""
    if not settings.ELEVENLABS_API_KEY:
        return True

    async with _client() as http:
        resp = await http.delete(f"{CONVAI_URL}/phone-numbers/{phone_number_id}")
        return resp.status_code in (200, 204, 404)


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════


async def create_kb_from_text(
    *,
    text: str,
    name: str | None = None,
) -> dict:
    """Create a knowledge base document from raw text.

    Returns {"id": "...", "name": "..."}.
    """
    payload: dict[str, Any] = {"text": text}
    if name:
        payload["name"] = name

    if not settings.ELEVENLABS_API_KEY:
        import uuid
        return {"id": f"kb_stub_{uuid.uuid4().hex[:12]}", "name": name or "stub"}

    async with _client() as http:
        resp = await http.post(f"{CONVAI_URL}/knowledge-base/text", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Created KB doc from text: {data['id']}")
        return data


async def create_kb_from_url(
    *,
    url: str,
    name: str | None = None,
) -> dict:
    """Create a knowledge base document by scraping a URL.

    Returns {"id": "...", "name": "..."}.
    """
    payload: dict[str, Any] = {"url": url}
    if name:
        payload["name"] = name

    if not settings.ELEVENLABS_API_KEY:
        import uuid
        return {"id": f"kb_stub_{uuid.uuid4().hex[:12]}", "name": name or url}

    async with _client() as http:
        resp = await http.post(f"{CONVAI_URL}/knowledge-base/url", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Created KB doc from URL: {data['id']}")
        return data


async def create_kb_from_file(
    *,
    file_content: bytes,
    filename: str,
    name: str | None = None,
) -> dict:
    """Upload a file to the knowledge base (PDF, TXT, DOCX, etc.).

    Returns {"id": "...", "name": "..."}.
    """
    if not settings.ELEVENLABS_API_KEY:
        import uuid
        return {"id": f"kb_stub_{uuid.uuid4().hex[:12]}", "name": name or filename}

    async with httpx.AsyncClient(timeout=60) as http:
        files = {"file": (filename, BytesIO(file_content))}
        data = {}
        if name:
            data["name"] = name

        resp = await http.post(
            f"{CONVAI_URL}/knowledge-base/file",
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            files=files,
            data=data,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Created KB doc from file '{filename}': {result['id']}")
        return result


async def list_knowledge_base() -> list[dict]:
    """List all knowledge base documents."""
    if not settings.ELEVENLABS_API_KEY:
        return []

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/knowledge-base")
        resp.raise_for_status()
        data = resp.json()
        return data.get("documents", [])


async def delete_kb_document(doc_id: str) -> bool:
    """Delete a knowledge base document."""
    if not settings.ELEVENLABS_API_KEY:
        return True

    async with _client() as http:
        resp = await http.delete(f"{CONVAI_URL}/knowledge-base/{doc_id}")
        return resp.status_code in (200, 204, 404)


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATIONS
# ══════════════════════════════════════════════════════════════════════════════


async def list_conversations(
    *,
    agent_id: str | None = None,
    page_size: int = 30,
    cursor: str | None = None,
) -> dict:
    """List conversations (calls + text chats) from ElevenLabs.

    Returns {"conversations": [...], "has_more": bool, "next_cursor": str | None}.
    """
    if not settings.ELEVENLABS_API_KEY:
        return {"conversations": [], "has_more": False, "next_cursor": None}

    params: dict[str, Any] = {"page_size": page_size}
    if agent_id:
        params["agent_id"] = agent_id
    if cursor:
        params["cursor"] = cursor

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/conversations", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_conversation(conversation_id: str) -> dict:
    """Get detailed conversation including transcript.

    Returns full conversation object with transcript turns, metadata, analysis.
    """
    if not settings.ELEVENLABS_API_KEY:
        return {"conversation_id": conversation_id, "transcript": [], "status": "done"}

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/conversations/{conversation_id}")
        resp.raise_for_status()
        return resp.json()


async def get_conversation_audio(conversation_id: str) -> bytes | None:
    """Download the audio recording of a conversation."""
    if not settings.ELEVENLABS_API_KEY:
        return None

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/conversations/{conversation_id}/audio")
        if resp.status_code == 200:
            return resp.content
        return None


# ══════════════════════════════════════════════════════════════════════════════
# WIDGET / SIGNED URL
# ══════════════════════════════════════════════════════════════════════════════


def get_widget_embed_code(agent_id: str) -> dict[str, str]:
    """Generate embed snippets for the voice widget.

    Returns both our custom voice-first widget (iframe) and the fallback
    ElevenLabs embed tag.  The custom widget is a full-screen React page
    served from the dashboard at /widget/{agent_id}.
    """
    platform_url = settings.PLATFORM_URL.rstrip("/")
    custom_widget_url = f"{platform_url}/widget/{agent_id}"

    # Custom widget — iframe embed (voice-first, no text mode)
    iframe_embed = (
        f'<iframe\n'
        f'  src="{custom_widget_url}"\n'
        f'  width="120"\n'
        f'  height="120"\n'
        f'  style="position:fixed;bottom:20px;right:20px;border:none;border-radius:50%;z-index:9999;overflow:hidden;"\n'
        f'  allow="microphone"\n'
        f'  title="Voice Assistant"\n'
        f'></iframe>'
    )

    # Fallback — standard ElevenLabs embed tag
    legacy_embed = (
        f'<elevenlabs-convai agent-id="{agent_id}"></elevenlabs-convai>\n'
        f'<script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>'
    )

    return {
        "iframe": iframe_embed,
        "legacy": legacy_embed,
        "widget_url": custom_widget_url,
    }


async def get_signed_url(agent_id: str) -> str | None:
    """Get a signed URL for secure widget access (if auth is configured on the agent).

    Returns the signed URL string or None if not supported.
    """
    if not settings.ELEVENLABS_API_KEY:
        return None

    async with _client() as http:
        resp = await http.get(f"{CONVAI_URL}/agents/{agent_id}/link")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("signed_url")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# VOICES
# ══════════════════════════════════════════════════════════════════════════════


async def list_voices() -> list[dict]:
    """List available ElevenLabs voices."""
    if not settings.ELEVENLABS_API_KEY:
        return [
            {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Rachel"},
            {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel (alt)"},
        ]

    async with _client() as http:
        resp = await http.get(f"{BASE_URL}/voices")
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "voice_id": v["voice_id"],
                "name": v.get("name", ""),
                "category": v.get("category", ""),
                "labels": v.get("labels", {}),
            }
            for v in data.get("voices", [])
        ]

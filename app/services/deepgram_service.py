"""Deepgram — temporary browser tokens and Voice Agent settings helpers."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services.omniweb_brain_service import compose_channel_prompt
from app.services.tool_registry import get_tool_definitions

logger = get_logger(__name__)
settings = get_settings()

DEEPGRAM_GRANT_URL = "https://api.deepgram.com/v1/auth/grant"
DEEPGRAM_AGENT_WS_URL = "wss://agent.deepgram.com/v1/agent/converse"
SARAH_ELEVENLABS_VOICE_ID = "nf4MCGNSdM0hxM95ZBQR"
ADAM_ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
LEGACY_DEFAULT_ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"

# Aura-2 voice gender lookup. Used to map a specific Aura model name in
# ``voice_override`` to the matching gender so the test console works whether
# it sends ``female``/``male`` keywords or a real Aura model id.
DEEPGRAM_AURA_FEMALE_VOICES = {
    "aura-2-amalthea-en", "aura-2-andromeda-en", "aura-2-asteria-en",
    "aura-2-athena-en", "aura-2-aurora-en", "aura-2-callista-en",
    "aura-2-cora-en", "aura-2-cordelia-en", "aura-2-delia-en",
    "aura-2-electra-en", "aura-2-harmonia-en", "aura-2-helena-en",
    "aura-2-hera-en", "aura-2-iris-en", "aura-2-janus-en",
    "aura-2-juno-en", "aura-2-luna-en", "aura-2-minerva-en",
    "aura-2-ophelia-en", "aura-2-pandora-en", "aura-2-phoebe-en",
    "aura-2-selene-en", "aura-2-thalia-en", "aura-2-vesta-en",
    "aura-asteria-en", "aura-athena-en", "aura-hera-en",
    "aura-luna-en", "aura-stella-en",
}
DEEPGRAM_AURA_MALE_VOICES = {
    "aura-2-apollo-en", "aura-2-arcas-en", "aura-2-aries-en",
    "aura-2-atlas-en", "aura-2-cronos-en", "aura-2-draco-en",
    "aura-2-helios-en", "aura-2-hermes-en", "aura-2-hyperion-en",
    "aura-2-jupiter-en", "aura-2-mars-en", "aura-2-neptune-en",
    "aura-2-odysseus-en", "aura-2-orion-en", "aura-2-orpheus-en",
    "aura-2-perseus-en", "aura-2-pluto-en", "aura-2-saturn-en",
    "aura-2-theo-en", "aura-2-uranus-en", "aura-2-zeus-en",
    "aura-arcas-en", "aura-orion-en", "aura-perseus-en",
    "aura-zeus-en",
}
DEEPGRAM_AURA_DEFAULT_FEMALE = "aura-2-asteria-en"
DEEPGRAM_AURA_DEFAULT_MALE = "aura-2-orion-en"
SUPPORTED_VOICE_LANGUAGE_CODES = {
    "en", "es", "fr", "de", "it", "pt", "nl", "sv", "ro",
    "ru", "uk", "pl",
    "ar", "tr",
    "hi", "bn",
    "zh", "ja", "ko",
    "id", "vi", "tl",
    "sw", "kri", "su",
    "multi",
}
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "sv": "Swedish",
    "ro": "Romanian",
    "ru": "Russian",
    "uk": "Ukrainian",
    "pl": "Polish",
    "ar": "Arabic",
    "tr": "Turkish",
    "hi": "Hindi",
    "bn": "Bengali",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "tl": "Filipino",
    "sw": "Swahili",
    "kri": "Krio",
    "su": "Sundanese",
    "multi": "the visitor's language",
}
VOICE_GREETING_TEMPLATES = {
    "es": "Hola, soy {agent_name} de {business_name}. Puedo ayudarte a encontrar exactamente lo que buscas, responder preguntas y asegurarme de que recibas la mejor ayuda. ¿Cómo puedo ayudarte hoy?",
    "fr": "Bonjour, je suis {agent_name} de {business_name}. Je peux vous aider à trouver exactement ce que vous cherchez, répondre à vos questions et vous guider vers la meilleure solution. Comment puis-je vous aider aujourd'hui ?",
    "de": "Hallo, ich bin {agent_name} von {business_name}. Ich kann Ihnen helfen, genau das zu finden, was Sie suchen, Fragen beantworten und Sie zur besten Lösung führen. Wie kann ich Ihnen heute helfen?",
    "it": "Ciao, sono {agent_name} di {business_name}. Posso aiutarti a trovare esattamente ciò che cerchi, rispondere alle tue domande e guidarti verso la soluzione migliore. Come posso aiutarti oggi?",
    "pt": "Olá, sou {agent_name} da {business_name}. Posso ajudar você a encontrar exatamente o que procura, responder perguntas e orientar você para a melhor solução. Como posso ajudar hoje?",
    "nl": "Hallo, ik ben {agent_name} van {business_name}. Ik kan u helpen precies te vinden wat u zoekt, vragen beantwoorden en u naar de beste oplossing begeleiden. Waarmee kan ik u vandaag helpen?",
    "sv": "Hej, jag är {agent_name} från {business_name}. Jag kan hjälpa dig hitta precis det du letar efter, svara på dina frågor och guida dig till den bästa lösningen. Hur kan jag hjälpa dig idag?",
    "ro": "Bună ziua, sunt {agent_name} de la {business_name}. Vă pot ajuta să găsiți exact ce căutați, să răspund la întrebări și să vă îndrept spre cea mai bună soluție. Cum vă pot ajuta astăzi?",
    "ru": "Здравствуйте, я {agent_name} из {business_name}. Я могу помочь вам найти именно то, что вы ищете, ответить на вопросы и подсказать лучшее решение. Чем я могу помочь сегодня?",
    "uk": "Вітаю, я {agent_name} з {business_name}. Я можу допомогти знайти саме те, що ви шукаєте, відповісти на запитання й підказати найкраще рішення. Чим можу допомогти сьогодні?",
    "pl": "Cześć, jestem {agent_name} z {business_name}. Mogę pomóc znaleźć dokładnie to, czego szukasz, odpowiedzieć na pytania i wskazać najlepsze rozwiązanie. Jak mogę dziś pomóc?",
    "ar": "مرحبًا، أنا {agent_name} من {business_name}. يمكنني مساعدتك في العثور على ما تبحث عنه بالضبط، والإجابة عن أسئلتك، وإرشادك إلى أفضل حل. كيف يمكنني مساعدتك اليوم؟",
    "tr": "Merhaba, ben {business_name} ekibinden {agent_name}. Aradığınız şeyi bulmanıza, sorularınızı yanıtlamanıza ve en doğru çözüme yönlendirmenize yardımcı olabilirim. Bugün size nasıl yardımcı olabilirim?",
    "hi": "नमस्ते, मैं {business_name} से {agent_name} हूं। मैं आपको ठीक वही खोजने, सवालों के जवाब देने और सही मदद पाने में सहायता कर सकता हूं। आज मैं आपकी कैसे मदद करूं?",
    "bn": "নমস্কার, আমি {business_name} থেকে {agent_name}। আমি আপনাকে প্রয়োজনীয় জিনিস খুঁজে পেতে, প্রশ্নের উত্তর দিতে এবং সেরা সমাধানের দিকে গাইড করতে পারি। আজ আমি কীভাবে সাহায্য করতে পারি?",
    "zh": "您好，我是来自 {business_name} 的 {agent_name}。我可以帮您找到想要的内容、回答问题，并引导您获得最合适的帮助。今天我能为您做什么？",
    "ja": "こんにちは、{business_name}の{agent_name}です。お探しのものを見つけたり、質問に答えたり、最適な案内をしたりできます。本日はどのようにお手伝いできますか？",
    "ko": "안녕하세요, {business_name}의 {agent_name}입니다. 찾으시는 것을 정확히 찾도록 돕고, 질문에 답하고, 가장 좋은 해결 방법을 안내해 드릴 수 있습니다. 오늘 무엇을 도와드릴까요?",
    "id": "Halo, saya {agent_name} dari {business_name}. Saya bisa membantu Anda menemukan apa yang dicari, menjawab pertanyaan, dan memandu Anda ke solusi terbaik. Bagaimana saya bisa membantu Anda hari ini?",
    "vi": "Xin chào, tôi là {agent_name} từ {business_name}. Tôi có thể giúp bạn tìm chính xác những gì cần, trả lời câu hỏi và hướng dẫn đến giải pháp tốt nhất. Hôm nay tôi có thể giúp gì cho bạn?",
    "tl": "Kumusta, ako si {agent_name} mula sa {business_name}. Matutulungan kita na mahanap ang hinahanap mo, sagutin ang iyong mga tanong, at gabayan ka sa pinakamahusay na solusyon. Paano kita matutulungan ngayon?",
    "sw": "Habari, mimi ni {agent_name} kutoka {business_name}. Ninaweza kukusaidia kupata unachotafuta, kujibu maswali yako, na kukuongoza kwenye suluhisho bora. Ninawezaje kukusaidia leo?",
    "kri": "Kushɛh, a nɛm {agent_name} fɔm {business_name}. A kɛn ɛp yu fɛn wetin yu de luk fɔ, ansa yu kwɛsɔn dɛn, ɛn ɛp yu gɛt di bɛs ansa. Aw a kɛn ɛp yu tɔde?",
    "su": "Wilujeng sumping, abdi {agent_name} ti {business_name}. Abdi tiasa ngabantosan anjeun mendakan naon anu anjeun milarian, ngajawab patarosan, sareng ngarahkeun kana solusi anu pangsaéna. Kumaha abdi tiasa ngabantosan anjeun dinten ieu?",
}


def _coerce_services(raw: Any) -> list[str]:
    """JSONB may be a list, legacy dict map, or empty; prompt code expects list[str]."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, dict):
        return [str(k).strip() for k in raw if str(k).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _coerce_business_hours(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_supported_languages(raw: Any) -> list[str]:
    if raw is None:
        return ["en"]
    if isinstance(raw, str):
        s = raw.strip().lower()
        return [s] if s else ["en"]
    if isinstance(raw, list):
        out = [str(x).lower().strip() for x in raw if str(x).strip()]
        return out if out else ["en"]
    return ["en"]


def _coerce_str_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, dict):
        return [str(v).strip() for v in raw.values() if str(v).strip()]
    return []


async def grant_temporary_token(ttl_seconds: int = 600) -> dict[str, Any]:
    if not settings.deepgram_configured:
        raise RuntimeError("DEEPGRAM_API_KEY is not configured")

    ttl = max(30, min(int(ttl_seconds), 3600))
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            DEEPGRAM_GRANT_URL,
            headers={
                "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"ttl_seconds": ttl},
        )
        if resp.status_code >= 400:
            logger.error(
                "Deepgram auth/grant failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        return resp.json()


def _tts_voice_for_config(config: AgentConfig) -> str:
    voice_id = (config.voice_id or "").strip()
    if "aura" in voice_id.lower():
        return voice_id
    return settings.DEEPGRAM_TTS_VOICE


def _deepgram_tts_for_language(language_tag: str, config: AgentConfig) -> str:
    """Return a Deepgram Aura voice model for the active language."""
    voice_id = (config.voice_id or "").strip()
    if voice_id and "aura" in voice_id.lower():
        return voice_id
    return settings.DEEPGRAM_TTS_VOICE


def _elevenlabs_voice_for_config(config: AgentConfig) -> str:
    """Return ElevenLabs voice id, falling back to default when config uses Aura."""
    voice_id = (config.voice_id or "").strip()
    if voice_id and voice_id != LEGACY_DEFAULT_ELEVENLABS_VOICE_ID and "aura" not in voice_id.lower():
        return voice_id
    default_voice_id = (settings.ELEVENLABS_DEFAULT_VOICE_ID or "").strip()
    if default_voice_id and default_voice_id != LEGACY_DEFAULT_ELEVENLABS_VOICE_ID:
        return default_voice_id
    return SARAH_ELEVENLABS_VOICE_ID


def _female_elevenlabs_voice_id() -> str:
    """ElevenLabs female voice — configured default falls back to Sarah."""
    configured = (settings.ELEVENLABS_DEFAULT_VOICE_ID or "").strip()
    if configured and configured != LEGACY_DEFAULT_ELEVENLABS_VOICE_ID:
        return configured
    return SARAH_ELEVENLABS_VOICE_ID


def _male_elevenlabs_voice_id() -> str:
    """ElevenLabs male voice — configured override falls back to Adam."""
    configured = (getattr(settings, "ELEVENLABS_MALE_VOICE_ID", "") or "").strip()
    return configured or ADAM_ELEVENLABS_VOICE_ID


def _voice_gender_from_override(voice_override: str | None) -> str | None:
    """Map a ``voice_override`` string to ``"female"``/``"male"``/``None``.

    Accepts both semantic keywords ("female", "male") sent by the test
    console and explicit Aura model names so older clients keep working.
    Returns ``None`` for unknown values so the caller falls through to the
    tenant's configured voice.
    """
    if not voice_override:
        return None
    raw = voice_override.strip().lower()
    if not raw:
        return None
    if raw in {"female", "f", "woman"}:
        return "female"
    if raw in {"male", "m", "man"}:
        return "male"
    if raw in DEEPGRAM_AURA_FEMALE_VOICES:
        return "female"
    if raw in DEEPGRAM_AURA_MALE_VOICES:
        return "male"
    return None


def _agent_language_tag(config: AgentConfig, requested: str | None = None) -> str:
    supported = [str(item).lower().strip() for item in (config.supported_languages or ["en"])]
    if requested:
        normalized = requested.lower().strip()
        if normalized == "multi":
            return "multi"
        if normalized in supported or any(lang.startswith(normalized) for lang in supported):
            return normalized[:8] if len(normalized) > 2 else normalized
    if len(supported) > 1:
        return "multi"
    if supported:
        return supported[0][:8]
    return "en"[:8]


def _deepgram_function_definitions() -> list[dict[str, Any]]:
    """Return Deepgram Voice Agent server-side function definitions."""
    retell_tools = get_tool_definitions(
        [
            "capture_lead",
            "send_services_email",
            "get_pricing",
            "check_availability",
            "book_appointment",
            "send_confirmation",
        ]
    )
    functions: list[dict[str, Any]] = []
    for tool in retell_tools:
        schema = tool.get("api_schema") or {}
        request_body = schema.get("request_body") or {}
        function_def: dict[str, Any] = {
            "name": tool.get("name"),
            "description": tool.get("description") or "",
            "parameters": request_body,
        }
        if schema.get("url"):
            function_def["endpoint"] = {
                "url": schema.get("url"),
                "method": str(schema.get("method") or "POST").lower(),
                "headers": schema.get("headers") or {},
            }
        if function_def.get("name"):
            functions.append(function_def)
    return functions


def build_voice_agent_settings(
    config: AgentConfig,
    language: str | None = None,
    voice_override: str | None = None,
) -> dict[str, Any]:
    language_tag = _agent_language_tag(config, language)
    composed = compose_channel_prompt(config, "web_voice", language=language_tag)
    think_model = (config.llm_model or "").strip() or settings.DEEPGRAM_AGENT_MODEL
    # Languages explicitly supported by Deepgram nova-3 STT with a named code.
    # Languages NOT listed here (Swahili, Krio, Sundanese) fall back to "multi" so
    # nova-3 at least attempts recognition rather than failing with an unknown code.
    _NOVA3_SUPPORTED = {
        "en", "es", "fr", "de", "it", "pt", "nl", "sv", "ro",
        "ru", "uk", "pl", "ar", "tr", "hi", "bn",
        "zh", "ja", "ko", "id", "vi", "tl",
    }
    if language_tag == "multi":
        listen_language = "multi"
    elif language_tag in _NOVA3_SUPPORTED:
        listen_language = language_tag
    else:
        # Unsupported STT code (sw, kri, su…) — use multi for best-effort recognition
        listen_language = "multi"

    # The widget can pin the spoken voice to a gender via ``voice_override``
    # (sent as ``female``/``male`` from the test console, or as a specific Aura
    # model name from older clients). When a gender is requested we line up an
    # ElevenLabs voice of that gender as the primary TTS and a matching Aura
    # voice as the deterministic fallback so the caller always hears the
    # gender they picked, even if ElevenLabs is unavailable.
    requested_gender = _voice_gender_from_override(voice_override)
    if requested_gender == "female":
        eleven_voice_id_for_gender = _female_elevenlabs_voice_id()
        deepgram_aura_for_gender = DEEPGRAM_AURA_DEFAULT_FEMALE
    elif requested_gender == "male":
        eleven_voice_id_for_gender = _male_elevenlabs_voice_id()
        deepgram_aura_for_gender = DEEPGRAM_AURA_DEFAULT_MALE
    else:
        eleven_voice_id_for_gender = None
        deepgram_aura_for_gender = None

    deepgram_model = (
        deepgram_aura_for_gender
        if deepgram_aura_for_gender
        else _deepgram_tts_for_language(language_tag, config)
    )
    deepgram_speak: dict[str, Any] = {
        "provider": {
            "type": "deepgram",
            "model": deepgram_model,
        }
    }

    if settings.ELEVENLABS_API_KEY:
        eleven_voice_id = eleven_voice_id_for_gender or _elevenlabs_voice_for_config(config)
        # Deepgram's Voice Agent ``agent.speak.provider`` only accepts the fields
        # documented in the API spec (``type``, ``model_id``, ``language_code``,
        # ``endpoint``). Sending extra keys like ``voice_settings`` makes Deepgram
        # reject the Settings frame with "Error parsing client message. Check the
        # agent.speak field against the API spec." Voice tuning is handled per
        # voice in the ElevenLabs dashboard instead, since Deepgram owns the
        # WebSocket BOS message that would otherwise carry voice_settings.
        # Do NOT pass language_code — eleven_turbo_v2_5 is natively multilingual
        # and auto-detects the language from the LLM-generated text.  Specifying
        # a code can cause ElevenLabs to reject languages it handles fine when
        # left to detect.
        speak: list[dict[str, Any]] | dict[str, Any] = [
            {
                "provider": {
                    "type": "eleven_labs",
                    "model_id": "eleven_turbo_v2_5",
                },
                "endpoint": {
                    "url": f"wss://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id}/multi-stream-input",
                    "headers": {"xi-api-key": settings.ELEVENLABS_API_KEY},
                },
            },
            deepgram_speak,
        ]
    else:
        speak = deepgram_speak

    listen_provider: dict[str, Any] = {
        "type": "deepgram",
        "model": settings.DEEPGRAM_STT_MODEL,
        "smart_format": True,
    }
    if listen_language != "multi":
        listen_provider["language"] = listen_language

    functions = _deepgram_function_definitions()

    # Shape must match Deepgram Voice Agent v1 Settings.
    # Provider-specific listen options belong inside agent.listen.provider.
    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 16000},
            "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
        },
        "agent": {
            "language": language_tag,
            "listen": {
                "provider": listen_provider,
            },
            "think": {
                "provider": {
                    "type": "open_ai",
                    "model": think_model,
                    "temperature": 0.65,
                },
                "prompt": composed,
                "functions": functions,
            },
            "speak": speak,
            "greeting": config.agent_greeting or "Hi there. How can I help you today?",
        },
    }


def transcript_lines_to_turns(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        role = str(line.get("role") or "user").strip().lower()
        content = str(line.get("content") or "").strip()
        if not content:
            continue
        speaker = "agent" if role == "assistant" else "caller"
        turns.append(
            {
                "speaker": speaker,
                "text": content,
                "timestamp": line.get("timestamp") or index,
            }
        )
    return turns


def summarize_transcript_fallback(turns: list[dict[str, Any]]) -> str | None:
    if not turns:
        return None

    caller_lines = [
        str(turn.get("text") or "").strip()
        for turn in turns
        if turn.get("speaker") == "caller"
    ]
    agent_lines = [
        str(turn.get("text") or "").strip()
        for turn in turns
        if turn.get("speaker") == "agent"
    ]
    caller_lines = [line for line in caller_lines if line]
    agent_lines = [line for line in agent_lines if line]

    if not caller_lines and not agent_lines:
        return None

    summary_parts: list[str] = []
    if caller_lines:
        summary_parts.append(f"Visitor asked about: {caller_lines[0][:180]}")
    if len(caller_lines) > 1:
        summary_parts.append(
            f"They exchanged {len(caller_lines)} visitor messages during the session"
        )
    if agent_lines:
        summary_parts.append(f"The assistant responded with guidance on {agent_lines[0][:140]}")

    return ". ".join(summary_parts).strip()[:500] or None


async def summarize_transcript(turns: list[dict[str, Any]]) -> str | None:
    if not turns:
        return None

    transcript_text = "\n".join(
        f"{str(turn.get('speaker') or 'unknown').upper()}: {str(turn.get('text') or '').strip()}"
        for turn in turns
        if str(turn.get("text") or "").strip()
    ).strip()
    if not transcript_text:
        return None

    if not settings.openai_configured:
        return summarize_transcript_fallback(turns)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You summarize website AI assistant conversations. Return JSON only "
                        "with keys: summary, sentiment. Keep summary to 1-2 sentences and "
                        "capture the user's goal and outcome."
                    ),
                },
                {"role": "user", "content": f"Transcript:\n{transcript_text}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=180,
        )
        raw = response.choices[0].message.content or "{}"
        payload = json.loads(raw)
        summary = str(payload.get("summary") or "").strip()
        if summary:
            return summary[:500]
        return summarize_transcript_fallback(turns)
    except Exception as exc:
        logger.warning("Deepgram widget summary generation failed", error=str(exc))
        return summarize_transcript_fallback(turns)

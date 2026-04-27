"""Deepgram — temporary browser tokens and Voice Agent settings helpers."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services.prompt_engine import compose_system_prompt

logger = get_logger(__name__)
settings = get_settings()

DEEPGRAM_GRANT_URL = "https://api.deepgram.com/v1/auth/grant"
DEEPGRAM_AGENT_WS_URL = "wss://agent.deepgram.com/v1/agent/converse"
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


async def grant_temporary_token(*, ttl_seconds: int = 600) -> dict[str, Any]:
    """Mint a short-lived JWT for browser Voice Agent / streaming APIs.

    Requires a Deepgram API key with at least Member role (see Deepgram token docs).
    """
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
    vid = (config.voice_id or "").strip()
    if not vid:
        return settings.DEEPGRAM_TTS_VOICE
    if vid.lower() == "aura-asteria-en":
        return "aura-2-asteria-en"
    if "aura" in vid.lower():
        return vid
    return settings.DEEPGRAM_TTS_VOICE


def _deepgram_tts_for_language(lang_tag: str, config: AgentConfig) -> str:
    if lang_tag.lower().startswith("es"):
        return "aura-2-aquila-es"
    return _tts_voice_for_config(config)


def _elevenlabs_voice_for_config(config: AgentConfig) -> str:
    vid = (config.voice_id or "").strip()
    if vid and "aura" not in vid.lower():
        return vid
    return settings.ELEVENLABS_DEFAULT_VOICE_ID


def _agent_language_tag(config: AgentConfig, requested: str | None) -> str:
    """BCP-47-ish tag for Voice Agent ``agent.language`` (``multi`` when appropriate)."""
    supported = _coerce_supported_languages(config.supported_languages)
    if requested:
        r = requested.lower().strip()
        if r in SUPPORTED_VOICE_LANGUAGE_CODES:
            return r[:8] if len(r) > 2 else r
        if any(s.startswith(r) for s in supported):
            return r[:8] if len(r) > 2 else r
    if len(supported) > 1:
        return "multi"
    return (supported[0] if supported else "en")[:8]


def _language_name(lang_tag: str) -> str:
    return LANGUAGE_NAMES.get(lang_tag.lower().split("-")[0], lang_tag)


DEFAULT_OPENING_GREETING = "Thank you for visiting today, I am your AI assistant... how can I assist you?"


def _is_stale_generic_greeting(text: str) -> bool:
    normalized = " ".join((text or "").lower().replace("’", "'").split())
    stale_markers = [
        "problem you're trying to solve",
        "problem you are trying to solve",
        "understand your needs",
        "recommend the right solution",
        "move forward faster by text or voice",
        "talk to me",
    ]
    return any(marker in normalized for marker in stale_markers)


def _opening_greeting(config: AgentConfig) -> str:
    greeting = (config.agent_greeting or "").strip()
    if greeting and not _is_stale_generic_greeting(greeting):
        return greeting

    return DEFAULT_OPENING_GREETING


def _localized_opening_greeting(config: AgentConfig, lang_tag: str) -> str:
    if lang_tag == "multi" or lang_tag.lower().startswith("en"):
        return _opening_greeting(config)

    language_code = lang_tag.lower().split("-")[0]
    template = VOICE_GREETING_TEMPLATES.get(language_code)
    if not template:
        return _opening_greeting(config)

    return template.format(
        agent_name=(config.agent_name or "Omniweb AI").strip(),
        business_name=(config.business_name or "this store").strip(),
    )


def build_voice_agent_settings(
    config: AgentConfig,
    *,
    language: str | None = None,
    voice_override: str | None = None,
) -> dict[str, Any]:
    """Build a Voice Agent ``Settings`` object (see Deepgram message-flow docs)."""
    composed = compose_system_prompt(
        agent_name=config.agent_name or "Alex",
        business_name=config.business_name or "",
        industry_slug=config.industry or "general",
        agent_mode=config.agent_mode,
        business_type=config.business_type,
        services=_coerce_services(config.services),
        business_hours=_coerce_business_hours(config.business_hours),
        timezone=config.timezone or "America/New_York",
        booking_url=config.booking_url,
        after_hours_message=config.after_hours_message or "",
        custom_prompt=config.system_prompt,
        custom_guardrails=_coerce_str_list(config.custom_guardrails),
        custom_escalation_triggers=_coerce_str_list(config.custom_escalation_triggers),
        custom_context=config.custom_context,
    )
    lang_tag = _agent_language_tag(config, language)
    opening_greeting = _localized_opening_greeting(config, lang_tag)
    language_instruction = (
        f"## Voice Language Requirement\n"
        f"CRITICAL LANGUAGE REQUIREMENT: The selected voice language is {_language_name(lang_tag)} ({lang_tag}). "
        f"This is higher priority than any business, sales, greeting, or language-matching instruction below. "
        f"Speak and respond only in {_language_name(lang_tag)} for this entire voice session. "
        f"Do not use English unless the selected voice language is English. "
        f"If the selected language is multi/the visitor's language, infer the visitor's language from speech and respond in that language.\n"
        f"If the shopper speaks English but selected {_language_name(lang_tag)}, still answer in {_language_name(lang_tag)}.\n\n"
        f"## Voice Session Opening\n"
        f"The voice session must begin with this complete welcome message. Do not shorten it, "
        f"skip the agent name, skip the business name, or replace it with a generic greeting:\n"
        f"\"{opening_greeting}\"\n\n"
        f"After the welcome message, wait for the user.\n\n"
        f"## Voice Focus And Background Noise\n"
        f"Treat short, unclear, distant, overlapping, or background speech as noise. "
        f"Only answer when a single nearby shopper clearly addresses the assistant. "
        f"Do not answer breathing, clicks, typing, TV/music, side conversations, or partial words. "
        f"If there is no clear request, remain silent and wait. "
        f"If a nearby shopper clearly addressed you but the words are unclear, ask them to repeat instead of guessing."
    )
    think_model = (config.llm_model or "").strip() or settings.DEEPGRAM_AGENT_MODEL
    # Languages explicitly supported by Deepgram nova-3 STT with a named code.
    # Languages NOT listed here (Swahili, Krio, Sundanese) fall back to "multi" so
    # nova-3 at least attempts recognition rather than failing with an unknown code.
    _NOVA3_SUPPORTED = {
        "en", "es", "fr", "de", "it", "pt", "nl", "sv", "ro",
        "ru", "uk", "pl", "ar", "tr", "hi", "bn",
        "zh", "ja", "ko", "id", "vi", "tl",
    }
    if lang_tag == "multi":
        listen_language = "multi"
    elif lang_tag in _NOVA3_SUPPORTED:
        listen_language = lang_tag
    else:
        # Unsupported STT code (sw, kri, su…) — use multi for best-effort recognition
        listen_language = "multi"

    # If a specific Deepgram Aura voice is requested (e.g. male from test console),
    # use Deepgram directly and skip ElevenLabs so the caller hears the correct voice.
    requested_aura = (voice_override or "").strip()
    use_aura_direct = bool(requested_aura and "aura" in requested_aura.lower())

    deepgram_model = requested_aura if use_aura_direct else _deepgram_tts_for_language(lang_tag, config)
    deepgram_speak: dict[str, Any] = {
        "provider": {
            "type": "deepgram",
            "model": deepgram_model,
        }
    }

    if settings.ELEVENLABS_API_KEY and not use_aura_direct:
        eleven_voice_id = _elevenlabs_voice_for_config(config)
        # Do NOT pass language_code — eleven_turbo_v2_5 is natively multilingual and
        # auto-detects the language from the LLM-generated text.  Specifying a code
        # can cause ElevenLabs to reject languages it handles fine when left to detect.
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

    # Shape must match Deepgram Voice Agent v1 Settings (see voice-agent-settings docs):
    # listen/speak/think use nested { "provider": { "type", "model", ... } }.
    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 16000},
            "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
        },
        "agent": {
            "greeting": opening_greeting,
            "listen": {
                "provider": {
                    "type": "deepgram",
                    "model": settings.DEEPGRAM_STT_MODEL,
                    "language": listen_language,
                    "smart_format": False,
                }
            },
            "think": {
                "provider": {
                    "type": "open_ai",
                    "model": think_model,
                    "temperature": 0.7,
                },
                "prompt": f"{language_instruction}\n\n{composed}",
            },
            "speak": speak,
        },
    }

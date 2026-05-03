from types import SimpleNamespace

from app.services import deepgram_service

SARAH_VOICE_ID = "nf4MCGNSdM0hxM95ZBQR"
LEGACY_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"


def _agent_config(**overrides):
    values = {
        "supported_languages": ["en"],
        "llm_model": None,
        "voice_id": None,
        "agent_name": "Alex",
        "agent_greeting": "Welcome to Omniweb. How can I help?",
        "business_name": "Omniweb",
        "business_type": None,
        "industry": "general",
        "agent_mode": "general_assistant",
        "system_prompt": "Be helpful.",
        "custom_instructions": "",
        "custom_context": "",
        "services": [],
        "business_hours": {},
        "timezone": "America/New_York",
        "booking_url": None,
        "after_hours_message": "",
        "custom_guardrails": [],
        "custom_escalation_triggers": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_voice_agent_settings_put_listen_language_inside_provider(monkeypatch):
    monkeypatch.setattr(
        deepgram_service,
        "settings",
        SimpleNamespace(
            DEEPGRAM_AGENT_MODEL="gpt-4o-mini",
            DEEPGRAM_STT_MODEL="nova-3",
            DEEPGRAM_TTS_VOICE="aura-asteria-en",
            ELEVENLABS_API_KEY="",
            ELEVENLABS_DEFAULT_VOICE_ID="voice-default",
        ),
    )

    settings = deepgram_service.build_voice_agent_settings(_agent_config(), language="en")
    listen = settings["agent"]["listen"]

    assert "language" not in listen
    assert "model" not in listen
    assert listen["provider"]["type"] == "deepgram"
    assert listen["provider"]["model"] == "nova-3"
    assert listen["provider"]["language"] == "en"
    assert "model" not in settings["agent"]["think"]
    assert settings["agent"]["think"]["provider"]["type"] == "open_ai"
    assert settings["agent"]["think"]["provider"]["model"] == "gpt-4o-mini"
    assert settings["agent"]["greeting"] == "Welcome to Omniweb. How can I help?"


def test_voice_agent_settings_omits_multi_listen_language(monkeypatch):
    monkeypatch.setattr(
        deepgram_service,
        "settings",
        SimpleNamespace(
            DEEPGRAM_AGENT_MODEL="gpt-4o-mini",
            DEEPGRAM_STT_MODEL="nova-3",
            DEEPGRAM_TTS_VOICE="aura-asteria-en",
            ELEVENLABS_API_KEY="",
            ELEVENLABS_DEFAULT_VOICE_ID="voice-default",
        ),
    )

    settings = deepgram_service.build_voice_agent_settings(
        _agent_config(supported_languages=["en", "es"]),
        language=None,
    )

    assert settings["agent"]["language"] == "multi"
    assert "language" not in settings["agent"]["listen"]["provider"]


def test_voice_agent_settings_replaces_legacy_elevenlabs_default(monkeypatch):
    monkeypatch.setattr(
        deepgram_service,
        "settings",
        SimpleNamespace(
            DEEPGRAM_AGENT_MODEL="gpt-4o-mini",
            DEEPGRAM_STT_MODEL="nova-3",
            DEEPGRAM_TTS_VOICE="aura-asteria-en",
            ELEVENLABS_API_KEY="test-key",
            ELEVENLABS_DEFAULT_VOICE_ID=LEGACY_VOICE_ID,
        ),
    )

    settings = deepgram_service.build_voice_agent_settings(
        _agent_config(voice_id=LEGACY_VOICE_ID),
        language="en",
    )

    speak = settings["agent"]["speak"]
    assert isinstance(speak, list)
    assert f"/text-to-speech/{SARAH_VOICE_ID}/" in speak[0]["endpoint"]["url"]

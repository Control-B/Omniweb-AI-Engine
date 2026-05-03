"""Asset-level checks for the universal embeddable widget.

The widget is shipped as a single self-contained ``app/static/widget.js``
that has to keep working from one snippet for omniweb.ai and customer
sites alike. These tests guard the public contract:

- script reads ``data-tenant-id`` / ``data-widget-key``
- it calls our handshake + Deepgram bootstrap routes
- it ports the audio watchdog + keepalive that prevent CLIENT_MESSAGE_TIMEOUT
- it does not re-introduce the assistant-greeting filter that previously
  swallowed the configured greeting.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.api.routes.widget import get_widget_script
from app.services.widget_service import WIDGET_SCRIPT_PATH

WIDGET_SOURCE = Path(WIDGET_SCRIPT_PATH).read_text(encoding="utf-8")


def test_widget_script_is_present_and_non_empty():
    assert WIDGET_SCRIPT_PATH.exists()
    assert len(WIDGET_SOURCE) > 1000


def test_widget_script_accepts_universal_snippet_attributes():
    assert 'getAttribute("data-tenant-id")' in WIDGET_SOURCE
    assert 'getAttribute("data-widget-key")' in WIDGET_SOURCE


def test_widget_script_calls_engine_endpoints():
    assert '"/api/widget/handshake"' in WIDGET_SOURCE
    assert '"/api/chat/voice-agent/bootstrap"' in WIDGET_SOURCE
    assert '"/api/widget/chat"' in WIDGET_SOURCE
    assert '"/api/chat/languages"' in WIDGET_SOURCE


def test_widget_script_passes_widget_key_to_voice_bootstrap():
    assert "widget_key:" in WIDGET_SOURCE
    assert "public_widget_key:" in WIDGET_SOURCE


def test_widget_script_keeps_audio_watchdog_and_keepalive():
    assert "_startWatchdog" in WIDGET_SOURCE
    assert "_startKeepAlive" in WIDGET_SOURCE
    assert "SILENCE_FALLBACK_MS" in WIDGET_SOURCE
    assert 'type: "KeepAlive"' in WIDGET_SOURCE


def test_widget_script_does_not_filter_assistant_greeting():
    assert "STALE_GENERIC_PATTERNS" not in WIDGET_SOURCE
    assert "normalizeAssistantCopy" not in WIDGET_SOURCE


def test_widget_script_renders_voice_and_text_modes_in_one_panel():
    assert "ow-mode voice" in WIDGET_SOURCE
    assert "ow-mode text" in WIDGET_SOURCE
    assert "Voice call" in WIDGET_SOURCE
    assert "Text chat" in WIDGET_SOURCE


def test_widget_script_uses_shadow_dom_and_blocks_text_zoom():
    assert "attachShadow" in WIDGET_SOURCE
    assert "text-size-adjust" in WIDGET_SOURCE


def test_get_widget_script_route_serves_javascript():
    response = asyncio.run(get_widget_script())
    assert response.media_type == "application/javascript"
    assert str(WIDGET_SCRIPT_PATH) == str(response.path)

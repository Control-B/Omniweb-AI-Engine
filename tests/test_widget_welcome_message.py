from types import SimpleNamespace

import pytest

from app.services import widget_service


def _client(**overrides):
    values = {
        "id": "client-uuid",
        "name": "Tenant",
        "public_widget_key": "public-key",
        "widget_enabled": True,
        "saas_widget_status": "active",
        "widget_installed": False,
        "widget_last_seen_at": None,
        "widget_primary_color": None,
        "widget_position": "bottom-right",
        "widget_welcome_message": None,
        "voice_enabled": True,
        "allowed_domains": [],
        "website_url": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _agent(**overrides):
    values = {
        "agent_name": "Sandy",
        "agent_greeting": (
            "Welcome! I am Sandy your AI assistant... I'm here to answer questions, "
            "recommend the right solution, and help you get the most value from our services. "
            "How may I help you today?"
        ),
        "agent_mode": "general_assistant",
        "business_name": "Sandy's Co.",
        "website_domain": None,
        "widget_config": {},
        "enabled_features": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_widget_welcome_prefers_current_agent_greeting():
    client = _client(widget_welcome_message="Old default welcome that drifted")
    agent = _agent()

    payload = widget_service.get_widget_settings_payload(client, agent)

    assert payload["widgetWelcomeMessage"] == agent.agent_greeting


def test_widget_welcome_falls_back_to_legacy_widget_message_when_agent_greeting_blank():
    client = _client(widget_welcome_message="Legacy welcome")
    agent = _agent(agent_greeting="")

    payload = widget_service.get_widget_settings_payload(client, agent)

    assert payload["widgetWelcomeMessage"] == "Legacy welcome"


def test_widget_welcome_falls_back_to_default_when_nothing_configured():
    client = _client(widget_welcome_message=None)
    agent = _agent(agent_greeting=None)

    payload = widget_service.get_widget_settings_payload(client, agent)

    assert payload["widgetWelcomeMessage"] == widget_service.DEFAULT_WELCOME_MESSAGE


@pytest.mark.parametrize("greeting", ["   ", "\n\n"])
def test_widget_welcome_treats_whitespace_only_greeting_as_unset(greeting):
    client = _client(widget_welcome_message="Legacy welcome")
    agent = _agent(agent_greeting=greeting)

    payload = widget_service.get_widget_settings_payload(client, agent)

    assert payload["widgetWelcomeMessage"] == "Legacy welcome"

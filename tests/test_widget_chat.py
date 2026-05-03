import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes import widget
from app.api.routes.saas import _widget_snippet
from app.api.routes.widget import WidgetChatIn, post_widget_chat


class _Db:
    async def commit(self):
        return None


class _Brain:
    def __init__(self, expected_tenant_id):
        self.expected_tenant_id = expected_tenant_id

    async def run(self, request):
        assert request.tenant_id == self.expected_tenant_id
        assert request.channel_type == "chat"
        assert request.user_message == "Do you repair water heaters?"
        assert request.metadata["provider"] == "omniweb_widget"
        return SimpleNamespace(response_text="Yes, we repair water heaters.")


def test_widget_snippet_uses_universal_tenant_id_attribute():
    snippet = _widget_snippet("https://engine.example", "public-key-123")

    assert snippet == (
        '<script src="https://engine.example/widget.js" '
        'data-tenant-id="public-key-123" async></script>'
    )


@pytest.mark.asyncio
async def test_widget_chat_uses_tenant_brain(monkeypatch):
    tenant_id = uuid4()
    client = SimpleNamespace(id=tenant_id)
    agent = SimpleNamespace(agent_mode="general_assistant")
    engagement = SimpleNamespace()

    async def validate_widget_request(_db, *, public_widget_id, domain):
        assert public_widget_id == "public-key-123"
        assert domain == "customer.example"
        return client, agent, "customer.example", ["customer.example"], "customer.example"

    async def get_or_create_widget_engagement(*_args, **_kwargs):
        return engagement

    monkeypatch.setattr(widget, "validate_widget_request", validate_widget_request)
    monkeypatch.setattr(widget, "mark_widget_seen", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(widget, "get_or_create_widget_engagement", get_or_create_widget_engagement)
    monkeypatch.setattr(widget, "append_widget_transcript", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(widget, "append_widget_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(widget, "OmniwebBrainService", lambda _db: _Brain(tenant_id))

    response = await post_widget_chat(
        WidgetChatIn(
            publicWidgetId="public-key-123",
            sessionId="session-123",
            message="Do you repair water heaters?",
            domain="customer.example",
            pageUrl="https://customer.example/",
        ),
        _Db(),
    )

    payload = json.loads(response.body)
    assert payload["success"] is True
    assert payload["data"]["message"]["content"] == "Yes, we repair water heaters."

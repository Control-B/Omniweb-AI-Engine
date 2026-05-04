from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes import chat
from app.api.routes.chat import ChatMessage, ChatRespondRequest, chat_respond


class _Db:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


class _Brain:
    def __init__(self, _db):
        pass

    async def run(self, request):
        return SimpleNamespace(
            response_text="I can send that over.",
            actions=[],
            escalation={},
            lead_fields={},
        )


@pytest.mark.asyncio
async def test_chat_respond_sends_requested_email_from_message_history(monkeypatch):
    tenant_id = uuid4()
    client = SimpleNamespace(id=tenant_id)
    db = _Db()
    sent = []

    async def resolve_client_by_public_identifier(_db, raw_id):
        assert raw_id == "public-key-123"
        return client

    async def fake_send_requested_email(_db, payload):
        sent.append(payload)
        return {"visitorEmail": True, "businessNotification": True}

    monkeypatch.setattr(chat, "resolve_client_by_public_identifier", resolve_client_by_public_identifier)
    monkeypatch.setattr(chat, "OmniwebBrainService", _Brain)
    monkeypatch.setattr(chat, "send_requested_email", fake_send_requested_email)

    response = await chat_respond(
        ChatRespondRequest(
            client_id="public-key-123",
            messages=[
                ChatMessage(role="user", content="Please send me more information."),
                ChatMessage(role="assistant", content="Sure, what email should I use?"),
                ChatMessage(role="user", content="My email is jane@example.com."),
            ],
            metadata={"session_id": "session-123", "page_url": "https://example.com"},
        ),
        db,
    )

    assert response["email_status"] == {"visitorEmail": True, "businessNotification": True}
    assert response["actions"] == [
        {
            "type": "send_email_notification",
            "payload": {
                "emailStatus": {"visitorEmail": True, "businessNotification": True},
                "recipient": "jane@example.com",
            },
        }
    ]
    assert len(sent) == 1
    assert sent[0].tenant_id == tenant_id
    assert sent[0].conversation_id == "session-123"
    assert sent[0].visitor_email == "jane@example.com"
    assert sent[0].source_url == "https://example.com"
    assert db.committed is True

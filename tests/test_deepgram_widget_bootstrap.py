from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import deepgram
from app.api.routes.deepgram import VoiceAgentBootstrapRequest, run_voice_agent_bootstrap


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, *results):
        self.results = list(results)
        self.execute_calls = 0

    async def get(self, _model, _entity_id):
        return None

    async def execute(self, _statement):
        self.execute_calls += 1
        if not self.results:
            raise AssertionError("unexpected execute call")
        return _Result(self.results.pop(0))


class _TenantDb(_Db):
    def __init__(self, client, agent):
        super().__init__(client, agent)
        self.client = client

    async def get(self, _model, entity_id):
        return self.client if entity_id == self.client.id else None


@pytest.mark.asyncio
async def test_voice_bootstrap_requires_explicit_tenant(monkeypatch):
    monkeypatch.setattr(
        deepgram,
        "settings",
        SimpleNamespace(deepgram_configured=True, LANDING_PAGE_CLIENT_ID=""),
    )
    db = _Db()

    with pytest.raises(HTTPException) as exc:
        await run_voice_agent_bootstrap(VoiceAgentBootstrapRequest(), db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "client_id or widget_key is required"
    assert db.execute_calls == 0


@pytest.mark.asyncio
async def test_voice_bootstrap_accepts_public_widget_key(monkeypatch):
    tenant_id = uuid4()
    client = SimpleNamespace(
        id=tenant_id,
        public_widget_key="public-key-123",
        stripe_subscription_id=None,
        subscription_status="trialing",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=6),
    )
    agent = SimpleNamespace(client_id=tenant_id, agent_name="Omniweb AI")
    db = _TenantDb(client, agent)

    async def grant_temporary_token(ttl_seconds):
        return {"access_token": "token", "expires_in": ttl_seconds}

    monkeypatch.setattr(
        deepgram,
        "settings",
        SimpleNamespace(deepgram_configured=True, LANDING_PAGE_CLIENT_ID=""),
    )
    monkeypatch.setattr(
        deepgram.deepgram_service,
        "grant_temporary_token",
        grant_temporary_token,
    )
    monkeypatch.setattr(
        deepgram.deepgram_service,
        "build_voice_agent_settings",
        lambda *_args, **_kwargs: {"agent": "settings"},
    )

    response = await run_voice_agent_bootstrap(
        VoiceAgentBootstrapRequest(widget_key="public-key-123", language="en"),
        db,
    )

    assert response["ok"] is True
    assert response["client_id"] == str(tenant_id)

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.models import Client
from app.services.saas_workspace_service import resolve_client_by_public_identifier
from app.services.widget_service import get_allowed_domains


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, client):
        self.client = client
        self.execute_calls = 0

    async def get(self, _model, entity_id):
        return self.client if entity_id == self.client.id else None

    async def execute(self, _statement):
        self.execute_calls += 1
        return _Result(self.client)


@pytest.mark.asyncio
async def test_resolve_public_identifier_accepts_client_uuid_without_query():
    client = Client(id=uuid4(), email="tenant@example.com", public_widget_key="public-key-123")
    db = _Db(client)

    resolved = await resolve_client_by_public_identifier(db, str(client.id))

    assert resolved is client
    assert db.execute_calls == 0


@pytest.mark.asyncio
async def test_resolve_public_identifier_accepts_public_widget_key():
    client = Client(id=uuid4(), email="tenant@example.com", public_widget_key="public-key-123")
    db = _Db(client)

    resolved = await resolve_client_by_public_identifier(db, "public-key-123")

    assert resolved is client
    assert db.execute_calls == 1


def test_allowed_domains_include_omniweb_for_universal_snippet():
    client = SimpleNamespace(allowed_domains=["customer.example"], website_url=None)

    assert get_allowed_domains(client, None) == ["customer.example", "omniweb.ai"]

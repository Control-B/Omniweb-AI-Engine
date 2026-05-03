from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.routes.assistant import AssistantScheduleRequest
from app.models.models import AppointmentRequest, EmailLog
from app.services import assistant_scheduling_service as svc
from app.services import email_service


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, *, client=None, results=None):
        self.client = client
        self.results = list(results or [])
        self.added = []
        self.flushed = False

    async def get(self, _model, entity_id):
        return self.client if self.client and entity_id == self.client.id else None

    async def execute(self, _statement):
        if not self.results:
            raise AssertionError("unexpected execute call")
        return _Result(self.results.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True


def _client(tenant_id):
    return SimpleNamespace(
        id=tenant_id,
        name="Acme Services",
        email="owner@example.com",
        notification_email="team@example.com",
    )


def _agent(tenant_id, **overrides):
    values = dict(
        client_id=tenant_id,
        business_name="Acme Services",
        booking_url=None,
        handoff_email=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_missing_visitor_email_is_rejected():
    with pytest.raises(ValidationError):
        AssistantScheduleRequest.model_validate(
            {
                "tenantId": str(uuid4()),
                "conversationId": "session-1",
                "visitorName": "Jane",
            }
        )


@pytest.mark.asyncio
async def test_valid_booking_url_returned_from_env_fallback(monkeypatch):
    tenant_id = uuid4()
    monkeypatch.setattr(
        svc,
        "settings",
        SimpleNamespace(
            CALCOM_BOOKING_URL="https://cal.com/acme/consult",
            CALCOM_BASE_URL="https://cal.com",
            CALCOM_EVENT_TYPE_ID="",
            CALCOM_DEFAULT_EVENT_TYPE_ID="",
        ),
    )
    db = _Db(client=_client(tenant_id), results=[_agent(tenant_id), None, None])

    appointment, _, _, duplicate = await svc.create_schedule_request(
        db,
        svc.SchedulePayload(
            tenant_id=tenant_id,
            conversation_id="session-1",
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            requested_service="Consultation",
        ),
    )

    assert duplicate is False
    assert appointment.booking_url == "https://cal.com/acme/consult"
    assert any(isinstance(obj, AppointmentRequest) for obj in db.added)


@pytest.mark.asyncio
async def test_tenant_booking_url_takes_priority(monkeypatch):
    tenant_id = uuid4()
    monkeypatch.setattr(
        svc,
        "settings",
        SimpleNamespace(CALCOM_BOOKING_URL="https://cal.com/default", CALCOM_BASE_URL="https://cal.com"),
    )
    db = _Db(client=_client(tenant_id), results=[_agent(tenant_id, booking_url="https://cal.com/acme/repair"), None, None])

    appointment, _, _, _ = await svc.create_schedule_request(
        db,
        svc.SchedulePayload(
            tenant_id=tenant_id,
            conversation_id="session-2",
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
        ),
    )

    assert appointment.booking_url == "https://cal.com/acme/repair"


@pytest.mark.asyncio
async def test_duplicate_scheduling_request_prevention():
    tenant_id = uuid4()
    existing = SimpleNamespace(
        id=uuid4(),
        booking_url="https://cal.com/acme/consult",
        conversation_id="session-1",
        visitor_email="jane@example.com",
        status="link_sent",
    )
    db = _Db(client=_client(tenant_id), results=[_agent(tenant_id), existing])

    appointment, _, _, duplicate = await svc.create_schedule_request(
        db,
        svc.SchedulePayload(
            tenant_id=tenant_id,
            conversation_id="session-1",
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
        ),
    )

    assert duplicate is True
    assert appointment is existing


@pytest.mark.asyncio
async def test_resend_email_success_logs_sent(monkeypatch):
    async def fake_send_email(**_kwargs):
        return True

    monkeypatch.setattr(email_service, "send_email", fake_send_email)
    db = _Db()

    ok = await email_service.sendVisitorConfirmationEmail(
        db,
        tenant_id=uuid4(),
        conversation_id="session-1",
        to="jane@example.com",
        business_name="Acme",
        visitor_name="Jane",
        visitor_email="jane@example.com",
        booking_url="https://cal.com/acme",
    )

    assert ok is True
    assert any(isinstance(obj, EmailLog) and obj.status == "sent" for obj in db.added)


@pytest.mark.asyncio
async def test_resend_email_failure_logs_failed(monkeypatch):
    async def fake_send_email(**_kwargs):
        return False

    monkeypatch.setattr(email_service, "send_email", fake_send_email)
    db = _Db()

    ok = await email_service.sendAppointmentRequestEmail(
        db,
        tenant_id=uuid4(),
        conversation_id="session-1",
        to="owner@example.com",
        business_name="Acme",
        visitor_name="Jane",
        visitor_email="jane@example.com",
        booking_url="https://cal.com/acme",
    )

    assert ok is False
    assert any(isinstance(obj, EmailLog) and obj.status == "failed" for obj in db.added)


def test_assistant_only_asks_for_missing_fields():
    state = svc.merge_schedule_state({}, "I want to book an appointment. My email is jane@example.com")

    assert svc.missing_schedule_fields(state) == ["name"]
    assert "name" in svc.missing_fields_prompt(["name"]).lower()
    assert "email" not in svc.missing_fields_prompt(["name"]).lower()


def test_mobile_widget_booking_button_rendering():
    script = open("app/static/widget.js", encoding="utf-8").read()

    assert "Book Appointment" in script
    assert "@media (max-width: 480px)" in script
    assert "Preparing booking link" in script

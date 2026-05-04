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


@pytest.mark.asyncio
async def test_schedule_emails_use_tenant_sender_and_notification_settings(monkeypatch):
    sent: list[dict] = []

    async def fake_send_email(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_email", fake_send_email)
    tenant_id = uuid4()
    client = _client(tenant_id)
    agent = _agent(tenant_id)
    scheduling_config = SimpleNamespace(
        settings_json={
            "notificationEmail": "dispatch@acme.test",
            "resendFromEmail": "Acme Appointments <appointments@acme.test>",
            "resendReplyToEmail": "frontdesk@acme.test",
        }
    )
    appointment = SimpleNamespace(
        conversation_id="session-1",
        visitor_name="Jane",
        visitor_email="jane@example.com",
        visitor_phone="555-111-2222",
        requested_service="Repair",
        preferred_date=None,
        preferred_time=None,
        notes="Need help",
        source_url="https://example.com",
        booking_url="https://cal.com/acme",
    )
    db = _Db(results=[scheduling_config])

    status = await svc.send_schedule_emails(db, appointment=appointment, client=client, agent=agent)

    assert status == {"visitorConfirmation": True, "businessNotification": True}
    assert sent[0]["to"] == "jane@example.com"
    assert sent[0]["from_email"] == "Acme Appointments <appointments@acme.test>"
    assert sent[0]["reply_to_email"] == "frontdesk@acme.test"
    assert sent[1]["to"] == "dispatch@acme.test"
    assert sent[1]["reply_to_email"] == "jane@example.com"


@pytest.mark.asyncio
async def test_requested_email_sends_visitor_and_team_notifications(monkeypatch):
    sent: list[dict] = []

    async def fake_send_email(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_email", fake_send_email)
    tenant_id = uuid4()
    scheduling_config = SimpleNamespace(
        settings_json={
            "notificationEmail": "team@acme.test",
            "resendFromEmail": "Acme <hello@acme.test>",
            "resendReplyToEmail": "support@acme.test",
        }
    )
    db = _Db(client=_client(tenant_id), results=[_agent(tenant_id), None, scheduling_config])

    status = await svc.send_requested_email(
        db,
        svc.EmailRequestPayload(
            tenant_id=tenant_id,
            conversation_id="session-email",
            visitor_email="visitor@example.com",
            visitor_name="Visitor",
            notes="Please email me more information.",
            source_url="https://example.com",
        ),
    )

    assert status == {"visitorEmail": True, "businessNotification": True}
    assert sent[0]["to"] == "visitor@example.com"
    assert sent[0]["from_email"] == "Acme <hello@acme.test>"
    assert sent[0]["reply_to_email"] == "support@acme.test"
    assert sent[1]["to"] == "team@acme.test"
    assert sent[1]["reply_to_email"] == "visitor@example.com"
    assert any(isinstance(obj, EmailLog) and obj.type == "visitor_requested_email" for obj in db.added)
    assert any(isinstance(obj, EmailLog) and obj.type == "lead_notification" for obj in db.added)


@pytest.mark.asyncio
async def test_requested_email_duplicate_is_not_resent(monkeypatch):
    async def fail_send_email(**_kwargs):
        raise AssertionError("duplicate email should not be sent")

    monkeypatch.setattr(email_service, "send_email", fail_send_email)
    tenant_id = uuid4()
    existing = SimpleNamespace(status="sent")
    db = _Db(client=_client(tenant_id), results=[_agent(tenant_id), existing])

    status = await svc.send_requested_email(
        db,
        svc.EmailRequestPayload(
            tenant_id=tenant_id,
            conversation_id="session-email",
            visitor_email="visitor@example.com",
            notes="Please send me information.",
        ),
    )

    assert status == {"visitorEmail": True, "businessNotification": True}


def test_email_request_intent_collects_only_email():
    state = svc.merge_email_request_state({}, "Please send me an email with more info")

    assert svc.has_email_request_intent("Please send me an email with more info") is True
    assert svc.missing_email_request_fields(state) == ["email"]
    assert "email" in svc.missing_email_fields_prompt().lower()


def test_build_email_request_payload_from_text_requires_intent_and_email():
    tenant_id = uuid4()
    payload = svc.build_email_request_payload_from_text(
        tenant_id=tenant_id,
        conversation_id="voice-session",
        text="Please send me the details. My name is Jane Doe and my email is jane@example.com.",
        source_url="https://example.com",
    )

    assert payload is not None
    assert payload.tenant_id == tenant_id
    assert payload.visitor_email == "jane@example.com"
    assert payload.visitor_name == "Jane Doe"
    assert payload.source_url == "https://example.com"
    assert svc.build_email_request_payload_from_text(
        tenant_id=tenant_id,
        conversation_id="voice-session",
        text="My email is jane@example.com.",
    ) is None


@pytest.mark.asyncio
async def test_verified_resend_sender_uses_tenant_from_email(monkeypatch):
    async def fake_domain_status(domain):
        assert domain == "acme.test"
        return "verified"

    monkeypatch.setattr(email_service, "_resend_domain_status", fake_domain_status)
    monkeypatch.setattr(
        email_service,
        "settings",
        SimpleNamespace(
            RESEND_API_KEY="resend-key",
            RESEND_FROM_EMAIL="Omniweb <noreply@omniweb.ai>",
            SMTP_FROM="",
            RESEND_REPLY_TO_EMAIL="",
        ),
    )

    resolved_from, resolved_reply_to, identity = await email_service._resolve_resend_from_email(
        "Acme <hello@acme.test>",
        "support@acme.test",
    )

    assert resolved_from == "Acme <hello@acme.test>"
    assert resolved_reply_to == "support@acme.test"
    assert identity["verified"] is True
    assert identity["fallback"] is False


@pytest.mark.asyncio
async def test_unverified_resend_sender_falls_back_to_platform_from(monkeypatch):
    async def fake_domain_status(domain):
        assert domain == "acme.test"
        return "pending"

    monkeypatch.setattr(email_service, "_resend_domain_status", fake_domain_status)
    monkeypatch.setattr(
        email_service,
        "settings",
        SimpleNamespace(
            RESEND_API_KEY="resend-key",
            RESEND_FROM_EMAIL="Omniweb <noreply@omniweb.ai>",
            SMTP_FROM="",
            RESEND_REPLY_TO_EMAIL="",
        ),
    )

    resolved_from, resolved_reply_to, identity = await email_service._resolve_resend_from_email(
        "Acme <hello@acme.test>",
        None,
    )

    assert resolved_from == "Omniweb <noreply@omniweb.ai>"
    assert resolved_reply_to == "hello@acme.test"
    assert identity["verified"] is False
    assert identity["fallback"] is True


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

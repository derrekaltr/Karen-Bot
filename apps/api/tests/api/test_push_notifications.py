"""Push notifications: device registration, what pings (and what doesn't),
transactional enqueue, and dead-token cleanup."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

HEADERS = {"X-User-Email": "dana@example.com"}
TOKEN = "ExponentPushToken[dana-iphone-123]"


class FakePushClient:
    """Scripted Expo stand-in: per-token ticket errors, scripted receipts."""

    def __init__(self, ticket_errors=None, receipt_errors=None):
        self.sent: list[dict] = []
        self.receipt_requests: list[list[str]] = []
        self.ticket_errors = ticket_errors or {}
        self.receipt_errors = receipt_errors or {}

    def send(self, messages):
        self.sent.extend(messages)
        tickets = []
        for m in messages:
            error = self.ticket_errors.get(m["to"])
            if error:
                tickets.append(
                    {"status": "error", "message": error, "details": {"error": error}}
                )
            else:
                tickets.append({"status": "ok", "id": f"r-{m['to']}"})
        return tickets

    def receipts(self, ids):
        self.receipt_requests.append(list(ids))
        out = {}
        for i in ids:
            error = self.receipt_errors.get(i)
            out[i] = (
                {"status": "error", "message": error, "details": {"error": error}}
                if error
                else {"status": "ok"}
            )
        return out


@pytest.fixture
def push_client():
    return FakePushClient()


@pytest.fixture
def client(db, push_client):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module
    from karenbot.agent.runner import AgentRuntime
    from karenbot.channels.mock_email import MockEmailAdapter
    from karenbot.llm.scripted import ScriptedClient
    from karenbot.simulator.personas import PERSONAS
    from karenbot.workflows.worker import Worker

    main_module._adapter = MockEmailAdapter(responder=PERSONAS["lowball_then_accept"])
    main_module._runtime = AgentRuntime(ScriptedClient())
    main_module._worker = Worker(
        main_module._adapter, main_module._runtime, worker_id="t", push_client=push_client
    )
    http = TestClient(main_module.app)
    assert http.post("/dev/seed").status_code == 200
    return http


def _jobs(db, job_type):
    from karenbot.domain.models import ScheduledJob

    with db() as s:
        return list(s.scalars(select(ScheduledJob).where(ScheduledJob.job_type == job_type)))


def _device(db, token):
    from karenbot.domain.models import PushDevice

    with db() as s:
        return s.scalars(select(PushDevice).where(PushDevice.token == token)).first()


def _make_user(db, email):
    from karenbot.domain.models import User

    with db() as s:
        user = User(email=email)
        s.add(user)
        s.commit()
        return user.id


def _case_to_approval(http) -> str:
    r = http.post(
        "/cases",
        headers=HEADERS,
        json={
            "company_name": "Acme Air",
            "category": "baggage_delay_expenses",
            "description": "Bag on AA 1234 delayed 3 days; spent $350 on essentials.",
            "requested_amount": "350.00",
        },
    )
    case_id = r.json()["case"]["id"]
    http.post(
        f"/cases/{case_id}/evidence",
        headers=HEADERS,
        json={"evidence_type": "receipt", "summary": "$350 receipts"},
    )
    assert http.post(f"/cases/{case_id}/intake/complete", headers=HEADERS).json()["eligible"]
    http.post(f"/cases/{case_id}/authorize", headers=HEADERS, json={"signed_name": "Dana Example"})
    assert http.post(f"/cases/{case_id}/contact", headers=HEADERS).json()["decision"] == "allow"
    for _ in range(3):
        http.post("/dev/tick", json={"ticks": 1})
    assert http.get(f"/cases/{case_id}", headers=HEADERS).json()["status"] == (
        "AWAITING_CUSTOMER_APPROVAL"
    )
    return case_id


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_validates_and_is_idempotent(client, db):
    r = client.post("/me/push-devices", headers=HEADERS, json={"token": TOKEN, "platform": "ios"})
    assert r.status_code == 200
    r = client.post("/me/push-devices", headers=HEADERS, json={"token": TOKEN, "platform": "ios"})
    assert r.status_code == 200

    from karenbot.domain.models import PushDevice

    with db() as s:
        assert len(list(s.scalars(select(PushDevice)))) == 1

    bad = client.post(
        "/me/push-devices", headers=HEADERS, json={"token": "not-a-token", "platform": "ios"}
    )
    assert bad.status_code == 422
    bad = client.post(
        "/me/push-devices", headers=HEADERS, json={"token": TOKEN, "platform": "windows"}
    )
    assert bad.status_code == 422


def test_requires_auth(client):
    r = client.post("/me/push-devices", json={"token": TOKEN, "platform": "ios"})
    assert r.status_code == 401


def test_token_moves_to_whoever_signs_in_on_the_phone(client, db):
    other_email = "sam@example.com"
    other_id = _make_user(db, other_email)
    other = {"X-User-Email": other_email}

    client.post("/me/push-devices", headers=HEADERS, json={"token": TOKEN, "platform": "ios"})
    # Sam signs in on Dana's old phone: alerts follow the signed-in account.
    client.post("/me/push-devices", headers=other, json={"token": TOKEN, "platform": "ios"})
    assert _device(db, TOKEN).user_id == other_id

    # Dana can't switch off Sam's phone.
    r = client.post("/me/push-devices/unregister", headers=HEADERS, json={"token": TOKEN})
    assert r.json() == {"removed": False}
    r = client.post("/me/push-devices/unregister", headers=other, json={"token": TOKEN})
    assert r.json() == {"removed": True}
    device = _device(db, TOKEN)
    assert device.disabled_at is not None and device.disabled_reason == "signed_out"

    # Signing back in re-enables it.
    client.post("/me/push-devices", headers=other, json={"token": TOKEN, "platform": "ios"})
    assert _device(db, TOKEN).disabled_at is None


# ---------------------------------------------------------------------------
# What pings
# ---------------------------------------------------------------------------


def test_offer_pings_the_phone_once_and_customer_actions_never_do(client, db, push_client):
    client.post("/me/push-devices", headers=HEADERS, json={"token": TOKEN, "platform": "ios"})
    case_id = _case_to_approval(client)

    # Enqueued during reply handling; delivered on the worker's next pass.
    client.post("/dev/tick", json={"ticks": 1})
    assert len(push_client.sent) == 1
    push = push_client.sent[0]
    assert push["to"] == TOKEN
    assert push["title"].startswith("Acme Air offered $")
    assert push["priority"] == "high"
    assert push["data"] == {"case_id": case_id, "event": "APPROVAL_REQUESTED"}

    # Ticket ok -> a receipts check is scheduled ~15 minutes out.
    receipts = _jobs(db, "push_receipts")
    assert len(receipts) == 1 and receipts[0].status == "pending"

    # The customer approves and confirms in the app: no pings for their own taps
    # (confirm-recovery runs as an agent CloseCase — the allowlist handles it).
    approval = client.get(f"/cases/{case_id}/approvals", headers=HEADERS).json()[0]
    client.post(f"/approvals/{approval['id']}/approve", headers=HEADERS)
    client.post("/dev/tick", json={"ticks": 2})
    assert client.post(f"/cases/{case_id}/confirm-recovery", headers=HEADERS).json()[
        "status"
    ] == "RESOLVED"
    client.post("/dev/tick", json={"ticks": 2})
    assert len(push_client.sent) == 1
    assert len(_jobs(db, "push_notification")) == 1


def test_no_phone_no_job(client, db, push_client):
    _case_to_approval(client)
    client.post("/dev/tick", json={"ticks": 1})
    assert _jobs(db, "push_notification") == []
    assert push_client.sent == []


def test_signed_out_phone_is_skipped_at_send_time(db):
    """Devices resolve when the job runs, not when it was queued."""
    from datetime import UTC, datetime

    from karenbot.domain.models import PushDevice, ScheduledJob, utcnow
    from karenbot.notifications.push import run_push_job

    user_id = _make_user(db, "lee@example.com")
    with db() as s:
        s.add(
            PushDevice(
                user_id=user_id,
                token=TOKEN,
                platform="ios",
                disabled_at=utcnow(),
                disabled_reason="signed_out",
            )
        )
        job = ScheduledJob(
            job_type="push_notification",
            run_at=datetime.now(UTC),
            payload={"user_id": str(user_id), "title": "t", "body": "b", "data": {}},
        )
        s.add(job)
        s.commit()
        fake = FakePushClient()
        run_push_job(s, job, fake)
        assert fake.sent == []


def test_retention_offer_copy_for_cancellations(client, db):
    from karenbot.domain.enums import ActorType, CaseEvent, CaseStatus
    from karenbot.domain.models import Case
    from karenbot.notifications.content import content_for_transition

    case_id = _case_to_approval(client)
    with db() as s:
        case = s.get(Case, uuid.UUID(case_id))
        case.category = "subscription_cancellation"
        content = content_for_transition(
            s,
            case,
            CaseEvent.APPROVAL_REQUESTED,
            actor_type=ActorType.AGENT,
            to_status=CaseStatus.AWAITING_CUSTOMER_APPROVAL,
        )
        assert content is not None
        assert content.title == "Acme Air is trying to keep you"

        # Never for customer-driven or non-allowlisted events.
        assert (
            content_for_transition(
                s,
                case,
                CaseEvent.APPROVAL_REQUESTED,
                actor_type=ActorType.CUSTOMER,
                to_status=CaseStatus.AWAITING_CUSTOMER_APPROVAL,
            )
            is None
        )
        assert (
            content_for_transition(
                s,
                case,
                CaseEvent.RECOVERY_VERIFIED,
                actor_type=ActorType.AGENT,
                to_status=CaseStatus.RESOLVED,
            )
            is None
        )


def test_money_formatting():
    from karenbot.notifications.content import format_money

    assert format_money(Decimal("1234.5"), "USD") == "$1,234.50"
    assert format_money(Decimal("80"), "eur") == "80.00 EUR"
    assert format_money(None, "USD") is None


def test_notification_bug_never_blocks_a_case(client, db, monkeypatch, push_client):
    import karenbot.notifications.push as push_module

    def boom(session, *args, **kwargs):
        # A real database error mid-enqueue (on Postgres this would abort the
        # whole transaction without the savepoint), then a Python one.
        from sqlalchemy import text

        session.execute(text("SELECT * FROM no_such_table"))
        raise RuntimeError("notification bug")

    monkeypatch.setattr(push_module, "content_for_transition", boom)
    client.post("/me/push-devices", headers=HEADERS, json={"token": TOKEN, "platform": "ios"})
    _case_to_approval(client)  # asserts the case still reached approval
    assert _jobs(db, "push_notification") == []


# ---------------------------------------------------------------------------
# Dead tokens
# ---------------------------------------------------------------------------


def test_dead_tokens_are_disabled_from_tickets_and_receipts(db):
    from datetime import UTC, datetime

    from karenbot.domain.models import PushDevice, ScheduledJob
    from karenbot.notifications.push import run_push_job, run_receipts_job

    user_id = _make_user(db, "pat@example.com")
    dead_now = "ExponentPushToken[dead-now]"
    dies_later = "ExponentPushToken[dies-later]"
    healthy = "ExponentPushToken[healthy]"
    with db() as s:
        for token in (dead_now, dies_later, healthy):
            s.add(PushDevice(user_id=user_id, token=token, platform="ios"))
        job = ScheduledJob(
            job_type="push_notification",
            run_at=datetime.now(UTC),
            payload={
                "user_id": str(user_id),
                "title": "t",
                "body": "b",
                "priority": "high",
                "data": {},
            },
        )
        s.add(job)
        s.commit()

        fake = FakePushClient(
            ticket_errors={dead_now: "DeviceNotRegistered"},
            receipt_errors={f"r-{dies_later}": "DeviceNotRegistered"},
        )
        run_push_job(s, job, fake)
        s.commit()
        assert {m["to"] for m in fake.sent} == {dead_now, dies_later, healthy}

        receipts_job = s.scalars(
            select(ScheduledJob).where(ScheduledJob.job_type == "push_receipts")
        ).one()
        assert set(receipts_job.payload["receipts"].values()) == {dies_later, healthy}
        run_receipts_job(s, receipts_job, fake)
        s.commit()

        status = {
            d.token: d.disabled_reason for d in s.scalars(select(PushDevice))
        }
        assert status == {
            dead_now: "DeviceNotRegistered",
            dies_later: "DeviceNotRegistered",
            healthy: None,
        }

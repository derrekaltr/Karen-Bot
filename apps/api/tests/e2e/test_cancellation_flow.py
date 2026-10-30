"""Subscription cancellation, end to end against the simulated company.

Clean path: cancel -> company confirms -> customer verifies billing stopped
-> RESOLVED with annual savings recorded and the charge marked canceled.

Retention path: company counters with a discount -> surfaces to the customer
as an approval -> customer DECLINES -> Karen reasserts -> company confirms.
"""

import pytest

USER = {"X-User-Email": "dana@example.com"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module
    from karenbot.channels.mock_email import MockEmailAdapter
    from karenbot.workflows.worker import Worker

    # Fresh adapter/worker per test: the mock adapter's per-recipient
    # exchange counts drive persona behavior and must not leak across tests.
    main_module._adapter = MockEmailAdapter(responder=None)
    main_module._worker = Worker(
        main_module._adapter, main_module._runtime, worker_id="cancel-test"
    )
    http = TestClient(main_module.app)
    http.post("/dev/seed")
    return http


def _start_cancellation(client) -> tuple[str, str]:
    """Link mock bank, cancel the Chipotle sub, authorize, contact.
    Returns (case_id, charge_id)."""
    client.post(
        "/banking/exchange",
        headers=USER,
        json={"public_token": "mock-public-token", "institution_name": "Mock Bank"},
    )
    subs = client.get("/banking/subscriptions", headers=USER).json()
    chipotle = next(s for s in subs if "Chipotle" in s["merchant_name"])
    r = client.post(
        f"/banking/subscriptions/{chipotle['id']}/action",
        headers=USER,
        json={"action": "cancel"},
    )
    case_id = r.json()["case_id"]
    client.post(f"/cases/{case_id}/authorize", headers=USER, json={"signed_name": "Dana"})
    r = client.post(f"/cases/{case_id}/contact", headers=USER)
    assert r.json()["decision"] == "allow"
    return case_id, chipotle["id"]


def _status(client, case_id: str) -> str:
    return client.get(f"/cases/{case_id}", headers=USER).json()["status"]


def _charge_status(client, charge_id: str) -> str:
    subs = client.get("/banking/subscriptions", headers=USER).json()
    return next(s for s in subs if s["id"] == charge_id)["status"]


def test_cancellation_email_reads_like_a_cancellation(client, db):
    case_id, _ = _start_cancellation(client)
    # The send happens on the worker tick (transactional outbox).
    client.post("/dev/tick", json={"persona": "cancels_cleanly", "ticks": 1})
    comms = client.get(f"/cases/{case_id}/communications", headers=USER).json()
    outbound = next(c for c in comms if c["direction"] == "outbound")
    assert "cancel the subscription" in outbound["body"].lower()
    assert "in writing" in outbound["body"].lower()
    # A cancellation is not a compensation claim.
    assert "reimburs" not in outbound["body"].lower()


def test_clean_cancellation_resolves_with_savings(client, db):
    case_id, charge_id = _start_cancellation(client)
    client.post("/dev/tick", json={"persona": "cancels_cleanly", "ticks": 4})
    assert _status(client, case_id) == "VERIFYING_RECOVERY"

    # Customer confirms the billing actually stopped.
    r = client.post(f"/cases/{case_id}/confirm-recovery", headers=USER)
    assert r.json()["status"] == "RESOLVED"
    assert _charge_status(client, charge_id) == "canceled"

    # Annual savings recorded: $9.99/month -> $119.88/year.
    from sqlalchemy import select

    from karenbot.domain.models import RecoveryOutcome

    session = db()
    outcome = session.scalars(
        select(RecoveryOutcome).order_by(RecoveryOutcome.created_at.desc())
    ).first()
    assert outcome is not None
    assert outcome.recovery_type == "subscription_savings"
    assert float(outcome.amount) == pytest.approx(119.88)
    assert outcome.verification_status == "verified_received"
    session.close()


def test_retention_offer_declined_then_cancelled(client, db):
    case_id, charge_id = _start_cancellation(client)

    # Company counters with a retention discount -> customer approval.
    client.post("/dev/tick", json={"persona": "retention_offer_then_cancel", "ticks": 3})
    assert _status(client, case_id) == "AWAITING_CUSTOMER_APPROVAL"
    approvals = client.get(f"/cases/{case_id}/approvals", headers=USER).json()
    assert len(approvals) == 1
    assert approvals[0]["action_type"] == "accept_offer"

    # Customer says no deal — keep canceling.
    r = client.post(f"/approvals/{approvals[0]['id']}/deny", headers=USER)
    assert r.status_code == 200
    assert r.json()["follow_up_queued"] is True

    # Karen's decline goes out; the company then confirms the cancellation.
    client.post("/dev/tick", json={"ticks": 5})
    assert _status(client, case_id) == "VERIFYING_RECOVERY"
    client.post(f"/cases/{case_id}/confirm-recovery", headers=USER)
    assert _status(client, case_id) == "RESOLVED"
    assert _charge_status(client, charge_id) == "canceled"


def test_deny_requires_pending_approval(client, db):
    case_id, _ = _start_cancellation(client)
    client.post("/dev/tick", json={"persona": "cancels_cleanly", "ticks": 4})
    # Nothing awaiting approval on the clean path.
    import uuid

    r = client.post(f"/approvals/{uuid.uuid4()}/deny", headers=USER)
    assert r.status_code == 404

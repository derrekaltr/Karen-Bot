"""Recurring-bill discovery: Plaid mock flow, moral-code routing, assist mode."""

import uuid

import pytest

from karenbot.discovery.service import normalize_merchant

USER = {"X-User-Email": "dana@example.com"}


def test_normalize_merchant():
    assert normalize_merchant("Chipotle Rewards+") == "chipotle"
    assert normalize_merchant("GymCo Fitness, LLC") == "gymco fitness"
    assert normalize_merchant("The StreamFlix Subscription") == "streamflix"


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    http = TestClient(main_module.app)
    http.post("/dev/seed")
    return http


def _link_and_refresh(http) -> list[dict]:
    r = http.post(
        "/banking/exchange",
        headers=USER,
        json={"public_token": "mock-public-token", "institution_name": "Mock Bank"},
    )
    assert r.status_code == 200, r.text
    subs = http.get("/banking/subscriptions", headers=USER).json()
    assert subs, "mock plaid should surface recurring charges"
    return subs


def test_link_token_and_exchange_with_mock_plaid(client):
    r = client.post("/banking/link-token", headers=USER)
    assert r.status_code == 200 and r.json()["link_token"].startswith("link-mock-")
    subs = _link_and_refresh(client)
    names = {s["merchant_name"] for s in subs}
    assert "StreamFlix" in names and "GymCo Fitness" in names
    streamflix = next(s for s in subs if s["merchant_name"] == "StreamFlix")
    assert float(streamflix["yearly_cost"]) == pytest.approx(22.99 * 12, abs=0.01)


def test_refresh_is_idempotent(client):
    first = _link_and_refresh(client)
    second = client.post("/banking/refresh", headers=USER).json()
    assert len(first) == len(second)  # upsert, not duplicate


def test_enterprise_merchant_gets_agent_case(client, db):
    """'Chipotle Rewards+' matches the seeded enterprise company Chipotle →
    full agent case."""
    subs = _link_and_refresh(client)
    chipotle = next(s for s in subs if "Chipotle" in s["merchant_name"])
    assert chipotle["company_targetable"] is True

    r = client.post(
        f"/banking/subscriptions/{chipotle['id']}/action",
        headers=USER,
        json={"action": "cancel"},
    )
    body = r.json()
    assert body["contact_mode"] == "agent"
    assert body["status"] == "AWAITING_AUTHORIZATION"

    # Authorize and contact: the agent itself sends (allow).
    case_id = body["case_id"]
    client.post(f"/cases/{case_id}/authorize", headers=USER, json={"signed_name": "Dana"})
    r = client.post(f"/cases/{case_id}/contact", headers=USER)
    assert r.json()["decision"] == "allow"
    assert r.json()["status"] == "CONTACTING_COMPANY"


def test_unknown_merchant_gets_assist_case_never_agent_send(client, db):
    """GymCo matches no known company → unclassified → assist mode: a draft
    for the customer, zero agent outreach (moral code)."""
    subs = _link_and_refresh(client)
    gym = next(s for s in subs if s["merchant_name"] == "GymCo Fitness")
    assert gym["company_targetable"] is False

    r = client.post(
        f"/banking/subscriptions/{gym['id']}/action", headers=USER, json={"action": "cancel"}
    )
    body = r.json()
    assert body["contact_mode"] == "assist"
    case_id = body["case_id"]

    client.post(f"/cases/{case_id}/authorize", headers=USER, json={"signed_name": "Dana"})
    r = client.post(f"/cases/{case_id}/contact", headers=USER)
    assert r.json()["decision"] == "allow"  # the DRAFT is allowed...
    # Re-clicking contact must not stack duplicate drafts.
    client.post(f"/cases/{case_id}/contact", headers=USER)

    comms = client.get(f"/cases/{case_id}/communications", headers=USER).json()
    drafts = [c for c in comms if c["classification"].get("draft_for_customer")]
    assert len(drafts) == 1, "assist mode must produce exactly one draft"
    assert "cancel" in drafts[0]["body"].lower()
    assert "KarenBot" not in drafts[0]["body"]  # customer's own voice
    # ...but nothing was queued for agent delivery.
    from sqlalchemy import select

    from karenbot.db.session import get_session_factory
    from karenbot.domain.models import OutboxMessage

    with get_session_factory()() as session:
        outbox_rows = session.scalars(
            select(OutboxMessage).where(OutboxMessage.case_id == uuid.UUID(case_id))
        ).all()
        assert outbox_rows == []


def test_refund_action_sets_requested_amount(client):
    subs = _link_and_refresh(client)
    streamflix = next(s for s in subs if s["merchant_name"] == "StreamFlix")
    r = client.post(
        f"/banking/subscriptions/{streamflix['id']}/action",
        headers=USER,
        json={"action": "refund"},
    )
    case = client.get(f"/cases/{r.json()['case_id']}", headers=USER).json()
    assert float(case["requested_amount"]) == 22.99
    assert case["category"] == "recurring_charge_refund"


def test_dismiss_and_action_idempotency(client):
    subs = _link_and_refresh(client)
    rosa = next(s for s in subs if "Rosa" in s["merchant_name"])
    r = client.post(
        f"/banking/subscriptions/{rosa['id']}/action", headers=USER, json={"action": "dismiss"}
    )
    assert r.json()["status"] == "dismissed"

    gym = next(s for s in subs if s["merchant_name"] == "GymCo Fitness")
    first = client.post(
        f"/banking/subscriptions/{gym['id']}/action", headers=USER, json={"action": "cancel"}
    ).json()
    second = client.post(
        f"/banking/subscriptions/{gym['id']}/action", headers=USER, json={"action": "cancel"}
    ).json()
    assert first["case_id"] == second["case_id"]  # no duplicate cases


def test_revoking_connection_drops_credentials(client, db):
    _link_and_refresh(client)
    connections = client.get("/banking/connections", headers=USER).json()
    r = client.post(f"/banking/connections/{connections[0]['id']}/revoke", headers=USER)
    assert r.json()["status"] == "revoked"

    from sqlalchemy import select

    from karenbot.db.session import get_session_factory
    from karenbot.domain.models import BankConnection

    with get_session_factory()() as session:
        row = session.scalars(select(BankConnection)).one()
        assert row.encrypted_access_token is None

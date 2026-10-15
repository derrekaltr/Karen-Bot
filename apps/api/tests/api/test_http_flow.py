"""Full case lifecycle over HTTP — the exact sequence the web UI drives."""

import pytest


@pytest.fixture
def client(db):
    # Import after `db` has pointed settings at the test database.
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module
    from karenbot.channels.mock_email import MockEmailAdapter
    from karenbot.simulator.personas import PERSONAS

    # Fresh adapter/worker per test (module singletons otherwise carry state).
    main_module._adapter = MockEmailAdapter(responder=PERSONAS["lowball_then_accept"])
    from karenbot.agent.runner import AgentRuntime
    from karenbot.llm.scripted import ScriptedClient
    from karenbot.workflows.worker import Worker

    main_module._runtime = AgentRuntime(ScriptedClient())
    main_module._worker = Worker(main_module._adapter, main_module._runtime, worker_id="t")
    # Rebuild the dev router against the fresh instances.
    test_client = TestClient(main_module.app)
    # Replace dev router state by calling tick through the worker directly.
    yield test_client, main_module


HEADERS = {"X-User-Email": "dana@example.com"}


def test_full_lifecycle_over_http(client):
    http, main_module = client

    # Seed demo data.
    r = http.post("/dev/seed")
    assert r.status_code == 200
    assert "Acme Air" in r.json()["companies"]

    # Companies list shows moral-code targetability.
    companies = {c["name"]: c for c in http.get("/companies").json()}
    assert companies["Acme Air"]["targetable"] is True
    assert companies["Rosa's Corner Bakery"]["targetable"] is False

    # Moral code over HTTP: small businesses get ASSIST mode (Karen drafts,
    # the customer sends) — never agent contact.
    r = http.post(
        "/cases",
        headers=HEADERS,
        json={
            "company_name": "Rosa's Corner Bakery",
            "category": "refund_request",
            "description": "x",
            "requested_amount": "20",
        },
    )
    assert r.status_code == 200
    assert r.json()["case"]["contact_mode"] == "assist"

    # Unknown companies work too: created unclassified -> assist mode.
    r = http.post(
        "/cases",
        headers=HEADERS,
        json={
            "company_name": "Totally New Gym LLC",
            "category": "subscription_cancellation",
            "description": "Cancel my membership please.",
            "requested_amount": None,
        },
    )
    assert r.status_code == 200
    assert r.json()["case"]["contact_mode"] == "assist"

    # Create a real case; Karen asks for missing evidence.
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
    assert r.status_code == 200, r.text
    body = r.json()
    case_id = body["case"]["id"]
    assert body["case"]["status"] == "AWAITING_INFORMATION"
    assert body["karen_questions"]

    # Provide evidence, complete intake -> eligible.
    assert (
        http.post(
            f"/cases/{case_id}/evidence",
            headers=HEADERS,
            json={"evidence_type": "receipt", "summary": "$350 receipts"},
        ).status_code
        == 200
    )
    r = http.post(f"/cases/{case_id}/intake/complete", headers=HEADERS)
    assert r.json()["eligible"] is True

    # Authorize with a typed signature; LOA text is returned.
    r = http.post(
        f"/cases/{case_id}/authorize", headers=HEADERS, json={"signed_name": "Dana Example"}
    )
    assert r.status_code == 200
    assert "LETTER OF AUTHORIZATION" in r.json()["loa_text"]
    assert r.json()["status"] == "READY_TO_CONTACT"

    # Karen drafts and queues the first email.
    r = http.post(f"/cases/{case_id}/contact", headers=HEADERS)
    assert r.json()["decision"] == "allow"

    # Simulated company: deliver + lowball + counter + concession.
    for _ in range(3):
        http.post("/dev/tick", json={"ticks": 1})

    r = http.get(f"/cases/{case_id}", headers=HEADERS)
    assert r.json()["status"] == "AWAITING_CUSTOMER_APPROVAL"

    # Approve the binding acceptance.
    approvals = http.get(f"/cases/{case_id}/approvals", headers=HEADERS).json()
    assert approvals and approvals[0]["action_type"] == "accept_offer"
    r = http.post(f"/approvals/{approvals[0]['id']}/approve", headers=HEADERS)
    assert r.json()["status"] == "VERIFYING_RECOVERY"

    # Confirm receipt -> resolved.
    r = http.post(f"/cases/{case_id}/confirm-recovery", headers=HEADERS)
    assert r.json()["status"] == "RESOLVED"

    # Timeline and audit are populated.
    comms = http.get(f"/cases/{case_id}/communications", headers=HEADERS).json()
    assert sum(1 for c in comms if c["direction"] == "outbound") >= 2
    assert sum(1 for c in comms if c["direction"] == "inbound") >= 2
    audit = http.get(f"/cases/{case_id}/audit", headers=HEADERS).json()
    assert any(e["event_type"] == "authorization.granted" for e in audit)


def test_revoke_kill_switch_over_http(client):
    http, _ = client
    http.post("/dev/seed")
    r = http.post(
        "/cases",
        headers=HEADERS,
        json={
            "company_name": "Acme Air",
            "category": "baggage_delay_expenses",
            "description": "Bag delayed.",
            "requested_amount": "100.00",
        },
    )
    case_id = r.json()["case"]["id"]
    r = http.post(f"/cases/{case_id}/revoke", headers=HEADERS)
    assert r.json()["status"] == "CANCELED"

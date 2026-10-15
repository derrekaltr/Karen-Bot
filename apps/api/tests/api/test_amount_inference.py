"""No amount field: Karen infers it, asks only as a fallback, and routes
no-target offers to the customer's judgment."""

import pytest

USER = {"X-User-Email": "dana@example.com"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module
    from karenbot.agent.runner import AgentRuntime
    from karenbot.channels.mock_email import MockEmailAdapter
    from karenbot.llm.scripted import ScriptedClient
    from karenbot.simulator.personas import PERSONAS
    from karenbot.workflows.worker import Worker

    main_module._adapter = MockEmailAdapter(responder=PERSONAS["lowball_then_accept"])
    main_module._runtime = AgentRuntime(ScriptedClient())
    main_module._worker = Worker(main_module._adapter, main_module._runtime, worker_id="t")
    http = TestClient(main_module.app)
    http.post("/dev/seed")
    return http, main_module


def test_amount_inferred_from_description(client):
    http, _ = client
    r = http.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "American Airlines",
            "category": "flight_credit_reissue",
            "description": "I have $840 in trip credits from flights I didn't take; "
            "the app says they expired.",
            "requested_amount": None,
        },
    )
    assert r.status_code == 200, r.text
    case = http.get(f"/cases/{r.json()['case']['id']}", headers=USER).json()
    assert float(case["requested_amount"]) == 840.0
    assert case["facts"]["amount_source"] == "stated_in_description"
    # No ballpark question needed — she found the number herself.
    assert not any("how much" in q.lower() for q in r.json()["karen_questions"])


def test_no_amount_asks_ballpark_and_routes_offer_to_customer(client):
    http, main_module = client
    r = http.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "Acme Air",
            "category": "baggage_delay_expenses",
            "description": "My bag vanished for a week and it ruined my trip.",
            "requested_amount": None,
        },
    )
    body = r.json()
    case_id = body["case"]["id"]
    assert any("how much" in q.lower() for q in body["karen_questions"])

    http.post(
        f"/cases/{case_id}/evidence",
        headers=USER,
        json={"evidence_type": "receipt", "summary": "photos and receipts"},
    )
    result = http.post(f"/cases/{case_id}/intake/complete", headers=USER).json()
    assert result["eligible"] is True
    http.post(f"/cases/{case_id}/authorize", headers=USER, json={"signed_name": "Dana"})
    r = http.post(f"/cases/{case_id}/contact", headers=USER)
    assert r.json()["decision"] == "allow"

    # Company replies with an offer; with no target amount Karen must NOT
    # auto-counter — the offer goes to the customer for approval.
    http.post("/dev/tick", json={"ticks": 2})
    case = http.get(f"/cases/{case_id}", headers=USER).json()
    assert case["status"] == "AWAITING_CUSTOMER_APPROVAL"
    approvals = http.get(f"/cases/{case_id}/approvals", headers=USER).json()
    assert approvals and approvals[0]["action_type"] == "accept_offer"

    # And no draft ever said "USD None".
    comms = http.get(f"/cases/{case_id}/communications", headers=USER).json()
    for comm in comms:
        assert "None" not in (comm["subject"] or "")
        assert "USD None" not in comm["body"]

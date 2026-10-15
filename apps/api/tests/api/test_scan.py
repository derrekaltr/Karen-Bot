"""Inbox scan: claim candidates and case-evidence matching."""

import pytest

USER = {"X-User-Email": "dana@example.com"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    http = TestClient(main_module.app)
    http.post("/dev/seed")
    return http


def test_scan_finds_claim_candidates(client):
    candidates = client.post("/scan/inbox", headers=USER).json()
    kinds = {c["kind"] for c in candidates}
    assert "unused_flight_credit" in kinds
    aa = next(c for c in candidates if c["kind"] == "unused_flight_credit")
    assert aa["company_name"] == "American Airlines"
    assert aa["suggested_category"] == "flight_credit_reissue"
    assert float(aa["amount"]) == 840.0


def test_candidate_becomes_case_and_disappears_from_scan(client):
    candidates = client.post("/scan/inbox", headers=USER).json()
    aa = next(c for c in candidates if c["company_name"] == "American Airlines")
    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": aa["company_name"],
            "category": aa["suggested_category"],
            "description": f"{aa['title']}. {aa['snippet']}",
            "requested_amount": aa["amount"],
        },
    )
    assert r.status_code == 200
    # Already-pursued candidates are not resurfaced.
    again = client.post("/scan/inbox", headers=USER).json()
    assert not any(
        c["company_name"] == "American Airlines"
        and c["suggested_category"] == "flight_credit_reissue"
        for c in again
    )


def test_case_evidence_scan_attaches_and_is_idempotent(client):
    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "Acme Air",
            "category": "baggage_delay_expenses",
            "description": "Bag delayed for days; I bought essentials costing $230.",
            "requested_amount": None,
        },
    )
    case_id = r.json()["case"]["id"]
    first = client.post(f"/scan/cases/{case_id}/evidence", headers=USER).json()
    assert first, "expected evidence hits for baggage keywords"
    assert any("receipt" in e["summary"].lower() for e in first)
    second = client.post(f"/scan/cases/{case_id}/evidence", headers=USER).json()
    assert second == []  # idempotent on scan references

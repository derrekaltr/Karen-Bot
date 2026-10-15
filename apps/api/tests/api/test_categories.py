"""Category catalog, custom categories, and the goodwill eligibility path."""

import pytest

USER = {"X-User-Email": "dana@example.com"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    http = TestClient(main_module.app)
    http.post("/dev/seed")
    return http


def test_catalog_has_industry_specific_options(client):
    data = client.get("/categories").json()
    airline = {c["key"] for c in data["by_industry"]["airline"]}
    assert "flight_credit_reissue" in airline
    assert "involuntary_downgrade" in airline
    assert "airline" in data["industries"]
    assert {c["key"] for c in data["general"]} == set(data["general_categories"])


def test_american_airlines_flight_credit_case_is_agent_mode(client):
    companies = {c["name"]: c for c in client.get("/companies").json()}
    aa = companies["American Airlines"]
    assert aa["targetable"] is True
    assert "flight_credit_reissue" in aa["claim_types"]

    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "American Airlines",
            "category": "flight_credit_reissue",
            "description": "I have $840 in trip credits from two flights I didn't "
            "take in March; the app says they expired.",
            "requested_amount": "840.00",
        },
    )
    assert r.status_code == 200, r.text
    case = r.json()["case"]
    assert case["contact_mode"] == "agent"

    # Flight credits are a goodwill-basis policy: eligibility passes.
    case_id = case["id"]
    client.post(f"/cases/{case_id}/intake/complete", headers=USER)
    detail = client.get(f"/cases/{case_id}", headers=USER).json()
    assert detail["status"] == "AWAITING_AUTHORIZATION"
    assert detail["eligibility_basis"] == "goodwill"


def test_unlisted_category_on_enterprise_pursued_as_goodwill(client):
    """A catalog or custom category with no company policy -> goodwill, not
    rejection — but policy-condition failures still reject."""
    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "Delta Air Lines",
            "category": "involuntary_downgrade",
            "description": "Paid for first, flew coach on DL 100.",
            "requested_amount": "400.00",
        },
    )
    case_id = r.json()["case"]["id"]
    client.post(
        f"/cases/{case_id}/evidence",
        headers=USER,
        json={"evidence_type": "receipt", "summary": "fare difference"},
    )
    result = client.post(f"/cases/{case_id}/intake/complete", headers=USER).json()
    assert result["eligible"] is True
    assert result["basis"] == "goodwill"


def test_policy_condition_failure_still_rejects(client):
    """Over the policy cap -> rejected, goodwill fallback must NOT rescue it."""
    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "Acme Air",
            "category": "baggage_delay_expenses",
            "description": "Lost bag, huge expenses.",
            "requested_amount": "99999.00",
        },
    )
    case_id = r.json()["case"]["id"]
    client.post(
        f"/cases/{case_id}/evidence",
        headers=USER,
        json={"evidence_type": "receipt", "summary": "receipts"},
    )
    result = client.post(f"/cases/{case_id}/intake/complete", headers=USER).json()
    assert result["eligible"] is False
    assert any("exceeds_policy_max" in reason for reason in result["reasons"])


def test_custom_category_free_text_normalized(client):
    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "Some Local Spa",
            "company_industry": "other",
            "category": "Gift Card They Refused To Honor",
            "description": "They refused my gift card.",
            "requested_amount": "75.00",
        },
    )
    assert r.status_code == 200, r.text
    case = r.json()["case"]
    assert case["category"] == "gift_card_they_refused_to_honor"
    assert case["contact_mode"] == "assist"


def test_unknown_company_with_industry_gets_catalogued(client):
    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "Budget Stay Hotels",
            "company_industry": "hotel",
            "category": "failed_reservation",
            "description": "Walked at midnight with a confirmed booking.",
            "requested_amount": "220.00",
        },
    )
    assert r.status_code == 200
    companies = {c["name"]: c for c in client.get("/companies").json()}
    assert companies["Budget Stay Hotels"]["industry"] == "hotel"
    assert companies["Budget Stay Hotels"]["targetable"] is False

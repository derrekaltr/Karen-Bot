"""User company profile: inbox-driven discovery, manual edits, conservatism."""

import pytest

USER = {"X-User-Email": "dana@example.com"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    return TestClient(main_module.app)


def _seed(client) -> None:
    assert client.post("/dev/seed").status_code == 200


def test_company_scan_maps_known_senders_only(client):
    _seed(client)
    r = client.post("/scan/companies", headers=USER)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "mock"
    # Mapped via domain labels / company-table tokens…
    assert set(body["found"]) == {
        "AT&T",
        "Delta Air Lines",
        "Uber",
        "American Express",
        "Acme Air",
    }
    # …and the random newsletter sender was NOT stored.
    mine = client.get("/me/companies", headers=USER).json()
    names = {c["company_name"] for c in mine}
    assert "randomblog" not in str(names).lower()
    assert names == set(body["found"])
    assert all(c["source"] == "email_scan" for c in mine)


def test_company_scan_idempotent(client):
    _seed(client)
    client.post("/scan/companies", headers=USER)
    second = client.post("/scan/companies", headers=USER).json()
    assert second["added"] == 0
    assert len(client.get("/me/companies", headers=USER).json()) == 5


def test_manual_add_and_remove(client):
    _seed(client)
    r = client.post(
        "/me/companies", headers=USER, json={"company_name": "Marriott"}
    )
    assert r.status_code == 200
    row = r.json()
    assert row["source"] == "manual"
    # Duplicate add returns the existing row.
    again = client.post(
        "/me/companies", headers=USER, json={"company_name": "Marriott"}
    ).json()
    assert again["id"] == row["id"]
    # Remove.
    assert client.delete(f"/me/companies/{row['id']}", headers=USER).json() == {
        "removed": True
    }
    assert client.get("/me/companies", headers=USER).json() == []


def test_profile_requires_known_user(client):
    _seed(client)
    client.post("/me/companies", headers=USER, json={"company_name": "Delta Air Lines"})
    # Dev auth rejects unknown accounts outright.
    other = {"X-User-Email": "other@example.com"}
    assert client.get("/me/companies", headers=other).status_code == 401
    row_id = client.get("/me/companies", headers=USER).json()[0]["id"]
    assert client.delete(f"/me/companies/{row_id}", headers=other).status_code == 401


def test_blank_manual_add_rejected(client):
    _seed(client)
    r = client.post("/me/companies", headers=USER, json={"company_name": "   "})
    assert r.status_code == 422


def test_expired_connection_is_a_409_not_an_empty_result(client, monkeypatch):
    """Dead OAuth grants must surface as 'reconnect', never as 'found nothing'."""
    _seed(client)
    from karenbot.channels.oauth import ReconnectRequired

    class ExpiredScanner:
        def scan_claims(self):
            raise ReconnectRequired("google")

        def list_senders(self):
            raise ReconnectRequired("google")

        def find_evidence(self, company_name, keywords):
            raise ReconnectRequired("google")

    import karenbot.api.scan as scan_module

    monkeypatch.setattr(
        scan_module, "get_inbox_scanner", lambda db, user: ExpiredScanner()
    )
    for call in (
        lambda: client.post("/scan/companies", headers=USER),
        lambda: client.post("/scan/inbox", headers=USER),
    ):
        response = call()
        assert response.status_code == 409
        assert "reconnect" in response.json()["detail"].lower()

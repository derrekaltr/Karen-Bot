"""Production catalog loader: real product data, zero demo bleed-through."""

import pytest

ADMIN = {"X-Admin-Token": "dev-admin"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    # Deliberately NOT calling /dev/seed — this simulates production.
    return TestClient(main_module.app)


def test_catalog_loads_product_data_only(client, db):
    r = client.post("/admin/catalog/load", headers=ADMIN)
    assert r.status_code == 200
    counts = r.json()
    assert counts["companies_added"] > 0
    assert counts["policies_added"] > 0

    from sqlalchemy import select

    from karenbot.domain.models import Company, OpsMember, SupportChannel

    session = db()
    names = {c.name for c in session.scalars(select(Company))}
    # Real enterprises in...
    assert {"Delta Air Lines", "Uber", "AT&T", "Marriott"} <= names
    # ...demo companies out.
    assert "Acme Air" not in names
    assert "Rosa's Corner Bakery" not in names

    # No fake channels, and nothing pre-verified: every channel awaits a
    # human verification in /admin before Karen may use it.
    channels = list(session.scalars(select(SupportChannel)))
    assert channels, "research channels should load"
    assert all(".example" not in c.address for c in channels)
    assert all(not c.verified for c in channels)

    # Founders on the council; the demo user is not.
    members = {m.email for m in session.scalars(select(OpsMember))}
    assert "derrekpbrown@gmail.com" in members
    assert "dana@example.com" not in members
    session.close()


def test_catalog_is_idempotent_and_preserves_human_edits(client, db):
    client.post("/admin/catalog/load", headers=ADMIN)

    from sqlalchemy import select

    from karenbot.domain.models import SupportChannel

    # A human verifies one channel...
    session = db()
    channel = session.scalars(select(SupportChannel)).first()
    channel.verified = True
    session.commit()
    channel_id = channel.id
    session.close()

    # ...and a re-load must not clobber it or duplicate anything.
    second = client.post("/admin/catalog/load", headers=ADMIN).json()
    assert second["companies_added"] == 0
    assert second["policies_added"] == 0
    session = db()
    assert session.get(SupportChannel, channel_id).verified is True
    session.close()


def test_catalog_requires_admin_token(client):
    assert client.post("/admin/catalog/load").status_code == 422
    assert (
        client.post("/admin/catalog/load", headers={"X-Admin-Token": "nope"}).status_code
        == 403
    )


def test_catalog_gives_intake_a_company_list(client):
    """The user-facing reason this exists: /companies is populated."""
    client.post("/admin/catalog/load", headers=ADMIN)
    companies = client.get("/companies").json()
    assert len(companies) >= 15
    delta = next(c for c in companies if c["name"] == "Delta Air Lines")
    assert delta["targetable"] is True
    assert "flight_delay_compensation" in delta["claim_types"]

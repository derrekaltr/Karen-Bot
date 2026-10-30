"""Claimable-events feed: public endpoints, admin review flow, research task."""

from datetime import UTC, datetime, timedelta

import pytest

ADMIN = {"X-Admin-Token": "dev-admin"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    return TestClient(main_module.app)


def _seed(client) -> None:
    r = client.post("/dev/seed")
    assert r.status_code == 200


def test_seed_publishes_demo_events_and_feed_lists_them(client):
    _seed(client)
    r = client.get("/events")
    assert r.status_code == 200
    events = r.json()
    assert len(events) == 2
    names = {e["company_name"] for e in events}
    assert names == {"Acme Air", "AT&T"}
    # Newest first; summary payload has no research notes or how_to_claim
    assert events[0]["event_date"] >= events[1]["event_date"]
    assert "research_notes" not in events[0]
    assert "how_to_claim" not in events[0]


def test_seed_demo_events_idempotent(client):
    _seed(client)
    _seed(client)
    assert len(client.get("/events").json()) == 2


def test_event_detail_published_only(client):
    _seed(client)
    event_id = client.get("/events").json()[0]["id"]
    detail = client.get(f"/events/{event_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["how_to_claim"]
    assert body["source_urls"]
    assert "research_notes" not in body


def test_draft_events_are_not_public(client):
    _seed(client)
    counts = client.post("/admin/events/research", headers=ADMIN).json()
    assert counts["created"] == 1  # scripted fixture event
    # Draft is invisible publicly...
    public = client.get("/events").json()
    assert all(e["company_name"] != "AT&T" or "Demo" in e["title"] for e in public)
    draft = client.get("/admin/events?status=draft", headers=ADMIN).json()
    assert len(draft) == 1
    event_id = draft[0]["id"]
    assert client.get(f"/events/{event_id}").status_code == 404
    # ...until published.
    r = client.post(f"/admin/events/{event_id}/publish", headers=ADMIN)
    assert r.status_code == 200
    assert client.get(f"/events/{event_id}").status_code == 200


def test_research_dedupes_on_rerun(client):
    _seed(client)
    first = client.post("/admin/events/research", headers=ADMIN).json()
    second = client.post("/admin/events/research", headers=ADMIN).json()
    assert first["created"] == 1
    assert second["created"] == 0
    assert second["skipped"] >= 1


def test_reject_hides_event_permanently(client):
    _seed(client)
    client.post("/admin/events/research", headers=ADMIN)
    event_id = client.get("/admin/events?status=draft", headers=ADMIN).json()[0]["id"]
    r = client.post(f"/admin/events/{event_id}/reject", headers=ADMIN)
    assert r.status_code == 200
    assert client.get(f"/events/{event_id}").status_code == 404
    # A rejected event can't be published.
    assert client.post(f"/admin/events/{event_id}/publish", headers=ADMIN).status_code == 409


def test_admin_events_require_token(client):
    _seed(client)
    assert client.get("/admin/events").status_code == 422  # missing header
    assert client.get("/admin/events", headers={"X-Admin-Token": "nope"}).status_code == 403
    assert client.post("/admin/events/research", headers={"X-Admin-Token": "nope"}).status_code == 403


def test_feed_window_excludes_old_events(client, db):
    _seed(client)
    from karenbot.domain.models import ClaimEvent

    session = db()
    old = ClaimEvent(
        company_name="Delta Air Lines",
        title="Old event outside the window",
        summary="x",
        event_date=(datetime.now(UTC) - timedelta(days=40)).date(),
        entitlement="x",
        eligibility="x",
        how_to_claim="x",
        category="flight_delay_compensation",
        source_urls=["https://example.com/old"],
        status="published",
        created_by="seed",
    )
    session.add(old)
    session.commit()
    session.close()
    assert all(e["company_name"] != "Delta Air Lines" for e in client.get("/events").json())
    # A wider window includes it (clamped at 31 days... 40 is still out)
    assert all(
        e["company_name"] != "Delta Air Lines"
        for e in client.get("/events?days=60").json()
    )

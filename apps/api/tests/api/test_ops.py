"""Ops Council: membership gate, item review flow, research agent."""

import pytest

OWNER = {"X-User-Email": "dana@example.com"}


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    http = TestClient(main_module.app)
    assert http.post("/dev/seed").status_code == 200
    return http


def _add_partner(client) -> dict:
    """Partner needs both a User row (dev auth) and ops membership."""
    from karenbot.db.session import get_session_factory
    from karenbot.domain.models import User

    session = get_session_factory()()
    session.add(User(email="partner@example.com", display_name="Pat Partner"))
    session.commit()
    session.close()
    r = client.post(
        "/ops/members",
        headers=OWNER,
        json={"email": "partner@example.com", "display_name": "Pat Partner"},
    )
    assert r.status_code == 200
    return {"X-User-Email": "partner@example.com"}


def test_non_members_are_locked_out(client):
    from karenbot.db.session import get_session_factory
    from karenbot.domain.models import User

    session = get_session_factory()()
    session.add(User(email="stranger@example.com"))
    session.commit()
    session.close()
    r = client.get("/ops/items", headers={"X-User-Email": "stranger@example.com"})
    assert r.status_code == 403
    assert "ops member" in r.json()["detail"]


def test_only_owners_add_members(client):
    partner = _add_partner(client)
    r = client.post(
        "/ops/members",
        headers=partner,
        json={"email": "friend@example.com", "display_name": "Friend"},
    )
    assert r.status_code == 403


def test_design_concept_review_round_trip(client):
    partner = _add_partner(client)

    # Partner submits a design concept to Dana for review.
    r = client.post(
        "/ops/items",
        headers=partner,
        json={
            "kind": "design_concept",
            "title": "Mascot on the loading screen",
            "body": "Karen should tap her foot while pages load.",
            "reviewer_email": "dana@example.com",
        },
    )
    assert r.status_code == 200
    item = r.json()
    assert item["status"] == "in_review"

    # It shows up in Dana's inbox, not the partner's.
    inbox = client.get("/ops/items?box=inbox", headers=OWNER).json()
    assert [i["id"] for i in inbox] == [item["id"]]
    assert client.get("/ops/items?box=inbox", headers=partner).json() == []

    # Dana requests changes with a comment.
    r = client.post(
        f"/ops/items/{item['id']}/request-changes",
        headers=OWNER,
        json={"comment": "Love it — but the foot tap needs to respect reduced motion."},
    )
    assert r.json()["status"] == "changes_requested"
    detail = client.get(f"/ops/items/{item['id']}", headers=partner).json()
    assert len(detail["comments"]) == 1

    # Partner comments and resubmits; Dana approves.
    client.post(
        f"/ops/items/{item['id']}/comments",
        headers=partner,
        json={"body": "Added a reduced-motion fallback."},
    )
    assert (
        client.post(f"/ops/items/{item['id']}/resubmit", headers=partner).json()[
            "status"
        ]
        == "in_review"
    )
    r = client.post(
        f"/ops/items/{item['id']}/approve", headers=OWNER, json={"comment": "Ship it."}
    )
    assert r.json()["status"] == "approved"
    assert r.json()["decided_at"] is not None


def test_only_assigned_reviewer_decides(client):
    partner = _add_partner(client)
    item = client.post(
        "/ops/items",
        headers=OWNER,
        json={
            "kind": "proposal",
            "title": "Pricing draft",
            "body": "$8/mo + 15% success fee.",
            "reviewer_email": "partner@example.com",
        },
    ).json()
    # The submitter can't approve their own item sent to someone else.
    r = client.post(f"/ops/items/{item['id']}/approve", headers=OWNER, json={})
    assert r.status_code == 403
    assert (
        client.post(f"/ops/items/{item['id']}/approve", headers=partner, json={})
        .json()["status"]
        == "approved"
    )


def test_reviewer_must_be_a_member(client):
    r = client.post(
        "/ops/items",
        headers=OWNER,
        json={
            "kind": "task",
            "title": "x",
            "body": "y",
            "reviewer_email": "nobody@example.com",
        },
    )
    assert r.status_code == 422


def test_research_run_creates_briefs(client):
    first = client.post("/ops/research/run", headers=OWNER).json()
    assert first["created"] == 1  # scripted fixture brief
    second = client.post("/ops/research/run", headers=OWNER).json()
    assert second["created"] == 0  # deduped by title
    briefs = client.get("/ops/items?box=research", headers=OWNER).json()
    assert len(briefs) == 1
    brief = briefs[0]
    assert brief["created_by_email"] == "karen-research"
    assert brief["recommendation"]
    assert brief["source_urls"]


def test_launch_checklist_seeded_and_metrics_visible(client):
    tasks = [
        i
        for i in client.get("/ops/items", headers=OWNER).json()
        if i["kind"] == "task"
    ]
    titles = {t["title"] for t in tasks}
    assert "Form the business entity" in titles
    assert "Rotate exposed secrets" in titles
    # Seed is idempotent.
    client.post("/dev/seed")
    again = [
        i
        for i in client.get("/ops/items", headers=OWNER).json()
        if i["kind"] == "task"
    ]
    assert len(again) == len(tasks)
    # Metrics are member-visible without the admin token.
    metrics = client.get("/ops/metrics", headers=OWNER)
    assert metrics.status_code == 200
    assert "recovered_total" in metrics.json()


def test_decisions_box_filters(client):
    client.post(
        "/ops/items",
        headers=OWNER,
        json={"kind": "decision", "title": "We punch up only", "body": "Moral code."},
    )
    decisions = client.get("/ops/items?box=decisions", headers=OWNER).json()
    assert len(decisions) == 1
    assert decisions[0]["kind"] == "decision"

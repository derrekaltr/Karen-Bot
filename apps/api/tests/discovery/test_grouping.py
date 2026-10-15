"""One case = one situation: trip grouping and ambiguity handling."""

from datetime import UTC, datetime

import pytest

from karenbot.discovery.grouping import extract_locator, group_hits, match_group_to_case
from karenbot.discovery.inbox_scan import EvidenceHit


def _hit(summary: str, snippet: str, day: int) -> EvidenceHit:
    return EvidenceHit(
        summary=summary,
        snippet=snippet,
        occurred_at=datetime(2026, 10, day, tzinfo=UTC),
        reference=f"gmail:{summary[:10]}{day}",
    )


JULY_TRIP = [
    EvidenceHit(
        "Email: Your flight to Miami - QUWSMF",
        "Confirmation code: QUWSMF Flight 3016",
        datetime(2026, 7, 18, tzinfo=UTC),
        "gmail:j1",
    ),
    EvidenceHit(
        "Email: Your flight to Los Angeles - QUWSMF",
        "Confirmation code: QUWSMF Flight 3328",
        datetime(2026, 7, 16, tzinfo=UTC),
        "gmail:j2",
    ),
]
OCT_TRIP = [
    EvidenceHit(
        "Email: Your seats changed",
        "Confirmation code: SMGTOK seat assignment flight 1689",
        datetime(2026, 10, 3, tzinfo=UTC),
        "gmail:o1",
    ),
    EvidenceHit(
        "Email: Your trip confirmation (MIA - SJU)",
        "Your trip confirmation and receipt. Issued October 3",  # no code
        datetime(2026, 10, 3, tzinfo=UTC),
        "gmail:o2",
    ),
]


def test_extract_locator():
    assert extract_locator("Confirmation code: QUWSMF your flight") == "QUWSMF"
    assert extract_locator("Email: Your flight to Miami - QUWSMF") == "QUWSMF"
    assert extract_locator("please UPDATE your CANCEL settings") is None


def test_groups_by_locator_and_date_clusters_codeless_emails():
    groups = group_hits(JULY_TRIP + OCT_TRIP)
    keys = {g.key for g in groups}
    assert keys == {"QUWSMF", "SMGTOK"}
    oct_group = next(g for g in groups if g.key == "SMGTOK")
    # The codeless trip-confirmation email date-clusters into the Oct trip.
    assert len(oct_group.hits) == 2
    # Newest trip first.
    assert groups[0].key == "SMGTOK"


def test_ambiguous_multi_trip_requires_user_choice():
    groups = group_hits(JULY_TRIP + OCT_TRIP)
    assert match_group_to_case(groups, "I missed my flights and want credits back") is None


def test_case_naming_a_locator_auto_selects():
    groups = group_hits(JULY_TRIP + OCT_TRIP)
    chosen = match_group_to_case(groups, "My trip SMGTOK to San Juan was a disaster")
    assert chosen is not None and chosen.key == "SMGTOK"


def test_single_trip_auto_selects():
    groups = group_hits(OCT_TRIP)
    chosen = match_group_to_case(groups, "anything")
    assert chosen is not None and chosen.key == "SMGTOK"


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    http = TestClient(main_module.app)
    http.post("/dev/seed")
    return http


USER = {"X-User-Email": "dana@example.com"}


def test_evidence_list_and_remove_endpoints(client):
    r = client.post(
        "/cases",
        headers=USER,
        json={
            "company_name": "Acme Air",
            "category": "baggage_delay_expenses",
            "description": "Bag gone. $200 of stuff bought.",
            "requested_amount": None,
        },
    )
    case_id = r.json()["case"]["id"]
    client.post(
        f"/cases/{case_id}/evidence",
        headers=USER,
        json={"evidence_type": "receipt", "summary": "receipts"},
    )
    items = client.get(f"/cases/{case_id}/evidence", headers=USER).json()
    assert len(items) == 1
    r = client.delete(f"/cases/{case_id}/evidence/{items[0]['id']}", headers=USER)
    assert r.status_code == 200
    assert client.get(f"/cases/{case_id}/evidence", headers=USER).json() == []

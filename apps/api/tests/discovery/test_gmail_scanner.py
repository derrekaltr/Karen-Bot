"""GmailInboxScanner against a faked Gmail search API, plus scanner selection."""


import httpx

from karenbot.discovery.gmail_scanner import GmailInboxScanner


def _fake_gmail(messages: list[dict]):
    """messages: [{id, subject, from, snippet, internalDate}]"""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/messages"):
            q = request.url.params.get("q", "")
            hits = [
                {"id": m["id"], "threadId": m.get("threadId", m["id"])}
                for m in messages
                if m.get("matches_query", True) and (m.get("only_query") in (None, q))
            ]
            return httpx.Response(200, json={"messages": hits[:int(request.url.params.get("maxResults", 10))]})
        msg_id = path.rsplit("/", 1)[-1]
        m = next((x for x in messages if x["id"] == msg_id), None)
        if m is None:
            return httpx.Response(404)
        return httpx.Response(
            200,
            json={
                "id": m["id"],
                "threadId": m.get("threadId", m["id"]),
                "snippet": m.get("snippet", ""),
                "internalDate": m.get("internalDate", "1760500000000"),
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": m.get("subject", "")},
                        {"name": "From", "value": m.get("from", "")},
                    ]
                },
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_scan_claims_parses_sender_amount_and_dedupes_threads():
    http = _fake_gmail(
        [
            {
                "id": "m1",
                "threadId": "t1",
                "subject": "Your flight to Miami - Delayed",
                "from": "American Airlines <no-reply@info.email.aa.com>",
                "snippet": "Flight AA 1689 was delayed 4 hours. Fare paid: $412.60.",
            },
            {
                "id": "m2",
                "threadId": "t1",  # same thread: must dedupe
                "subject": "Re: Your flight to Miami - Delayed",
                "from": "American Airlines <no-reply@info.email.aa.com>",
                "snippet": "duplicate thread entry",
            },
        ]
    )
    scanner = GmailInboxScanner(lambda: "tok", http=http)
    candidates = scanner.scan_claims()
    assert len(candidates) == 1
    c = candidates[0]
    assert c.company_name == "American Airlines"
    assert float(c.amount) == 412.60
    assert c.reference == "gmail:m1"
    assert c.company_industry in ("airline", "ecommerce")


def test_find_evidence_formats_hits():
    http = _fake_gmail(
        [
            {
                "id": "e1",
                "subject": "Your trip confirmation (MIA - SJU)",
                "from": "American Airlines <no-reply@info.email.aa.com>",
                "snippet": "Confirmation SMGTOK. AA 1689 MIA-SJU.",
                "internalDate": "1760000000000",
            }
        ]
    )
    scanner = GmailInboxScanner(lambda: "tok", http=http)
    hits = scanner.find_evidence("American Airlines", ["missed_flight_recovery", "flight"])
    assert len(hits) == 1
    assert "Your trip confirmation" in hits[0].summary
    assert "American Airlines" in hits[0].summary
    assert hits[0].reference == "gmail:e1"


def test_scanner_selection_prefers_connected_gmail(db):
    from karenbot.discovery.gmail_scanner import GmailInboxScanner as Live
    from karenbot.discovery.inbox_scan import MockInboxScanner, get_inbox_scanner
    from karenbot.domain.models import ConnectedAccount, User
    from karenbot.security.crypto import encrypt_json

    with db() as session:
        user = User(email="live@example.com")
        session.add(user)
        session.flush()
        assert isinstance(get_inbox_scanner(session, user), MockInboxScanner)

        session.add(
            ConnectedAccount(
                user_id=user.id,
                provider="gmail",
                provider_account_id="live@example.com",
                encrypted_token_reference=encrypt_json({"access_token": "x"}),
            )
        )
        session.flush()
        assert isinstance(get_inbox_scanner(session, user), Live)

"""GmailAdapter against a faked Gmail REST API (httpx.MockTransport)."""

import base64
import json
from email import message_from_bytes

import httpx

from karenbot.channels.base import OutboundMessage
from karenbot.channels.gmail import GmailAdapter
from karenbot.channels.mime_utils import build_mime, message_id_for_key


class FakeGmail:
    """Minimal users.messages fake: send, list (rfc822msgid + inbox), get."""

    def __init__(self):
        self.messages: dict[str, dict] = {}
        self.counter = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/messages/send") and request.method == "POST":
            payload = json.loads(request.read())
            raw = base64.urlsafe_b64decode(payload["raw"])
            mime = message_from_bytes(raw)
            self.counter += 1
            msg_id = f"g{self.counter}"
            thread = payload.get("threadId") or f"t{self.counter}"
            self.messages[msg_id] = {
                "id": msg_id,
                "threadId": thread,
                "rfc822msgid": (mime["Message-ID"] or "").strip("<>"),
                "raw": payload["raw"],
                "labels": ["SENT"],
            }
            return httpx.Response(200, json={"id": msg_id, "threadId": thread})
        if path.endswith("/messages") and request.method == "GET":
            q = request.url.params.get("q", "")
            if q.startswith("rfc822msgid:"):
                wanted = q.removeprefix("rfc822msgid:")
                found = [
                    {"id": m["id"], "threadId": m["threadId"]}
                    for m in self.messages.values()
                    if m["rfc822msgid"] == wanted
                ]
                return httpx.Response(200, json={"messages": found})
            inbox = [
                {"id": m["id"], "threadId": m["threadId"]}
                for m in self.messages.values()
                if "INBOX" in m["labels"]
            ]
            return httpx.Response(200, json={"messages": inbox})
        if "/messages/" in path and request.method == "GET":
            msg_id = path.rsplit("/", 1)[-1]
            m = self.messages[msg_id]
            return httpx.Response(
                200, json={"id": m["id"], "threadId": m["threadId"], "raw": m["raw"]}
            )
        return httpx.Response(404)

    def add_inbound(self, body: str, thread_id: str, in_reply_to: str | None = None) -> None:
        msg = build_mime(
            OutboundMessage(
                idempotency_key=f"sim:{len(self.messages)}",
                recipient_address="dana@example.com",
                subject="Re: your request",
                body=body,
            ),
            from_addr="support@corp.example",
            in_reply_to=in_reply_to,
        )
        self.counter += 1
        msg_id = f"g{self.counter}"
        self.messages[msg_id] = {
            "id": msg_id,
            "threadId": thread_id,
            "rfc822msgid": (msg["Message-ID"] or "").strip("<>"),
            "raw": base64.urlsafe_b64encode(msg.as_bytes()).decode(),
            "labels": ["INBOX"],
        }


def make_adapter(fake: FakeGmail) -> GmailAdapter:
    return GmailAdapter(
        token_getter=lambda: "test-token",
        from_addr="dana@example.com",
        http=httpx.Client(transport=httpx.MockTransport(fake.handler)),
    )


OUT = OutboundMessage(
    idempotency_key="case:c1:action:a1",
    recipient_address="support@corp.example",
    subject="Refund request",
    body="Please refund USD 350.",
)


def test_send_and_provider_side_idempotency():
    fake = FakeGmail()
    adapter = make_adapter(fake)
    receipt1 = adapter.send(OUT)
    receipt2 = adapter.send(OUT)  # same idempotency key: must not send twice
    assert receipt1 == receipt2
    sent = [m for m in fake.messages.values() if "SENT" in m["labels"]]
    assert len(sent) == 1


def test_find_by_idempotency_key():
    fake = FakeGmail()
    adapter = make_adapter(fake)
    assert adapter.find_by_idempotency_key("case:c1:action:a1") is None
    receipt = adapter.send(OUT)
    found = adapter.find_by_idempotency_key("case:c1:action:a1")
    assert found is not None and found.provider_message_id == receipt.provider_message_id


def test_fetch_inbound_prefers_gmail_thread_id():
    fake = FakeGmail()
    adapter = make_adapter(fake)
    receipt = adapter.send(OUT)
    fake.add_inbound(
        "We can offer you $175.",
        thread_id=receipt.provider_thread_id,
        in_reply_to=message_id_for_key(OUT.idempotency_key),
    )
    inbound = adapter.fetch_inbound()
    assert len(inbound) == 1
    assert inbound[0].provider_thread_id == receipt.provider_thread_id
    assert "offer you $175" in inbound[0].body

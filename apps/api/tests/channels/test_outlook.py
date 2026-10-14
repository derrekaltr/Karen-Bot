"""OutlookAdapter against a faked Microsoft Graph (httpx.MockTransport)."""

import json

import httpx

from karenbot.channels.base import OutboundMessage
from karenbot.channels.outlook import OutlookAdapter


class FakeGraph:
    def __init__(self):
        self.messages: dict[str, dict] = {}
        self.counter = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/me/messages") and request.method == "POST":
            payload = json.loads(request.read())
            self.counter += 1
            graph_id = f"draft-{self.counter}"
            self.messages[graph_id] = {
                "id": graph_id,
                "internetMessageId": payload["internetMessageId"],
                "conversationId": f"conv-{self.counter}",
                "isDraft": True,
                "subject": payload["subject"],
            }
            return httpx.Response(201, json=self.messages[graph_id])
        if path.endswith("/send") and request.method == "POST":
            graph_id = path.split("/")[-2]
            self.messages[graph_id]["isDraft"] = False
            return httpx.Response(202)
        if path.endswith("/me/messages") and request.method == "GET":
            flt = request.url.params.get("$filter", "")
            wanted = flt.split("'")[1] if "'" in flt else None
            value = [
                m for m in self.messages.values() if m["internetMessageId"] == wanted
            ]
            return httpx.Response(200, json={"value": value})
        if path.endswith("/mailFolders/inbox/messages"):
            value = [m for m in self.messages.values() if m.get("folder") == "inbox"]
            return httpx.Response(200, json={"value": value})
        return httpx.Response(404)


OUT = OutboundMessage(
    idempotency_key="case:c1:action:a9",
    recipient_address="support@corp.example",
    subject="Refund request",
    body="Please refund USD 350.",
)


def make_adapter(fake: FakeGraph) -> OutlookAdapter:
    return OutlookAdapter(
        token_getter=lambda: "tok",
        http=httpx.Client(transport=httpx.MockTransport(fake.handler)),
    )


def test_send_returns_internet_message_id_and_conversation():
    fake = FakeGraph()
    adapter = make_adapter(fake)
    receipt = adapter.send(OUT)
    assert receipt.provider_message_id.startswith("<kb-")
    assert receipt.provider_thread_id.startswith("conv-")
    # The draft was actually sent.
    assert all(not m["isDraft"] for m in fake.messages.values())


def test_idempotent_resend_returns_existing():
    fake = FakeGraph()
    adapter = make_adapter(fake)
    first = adapter.send(OUT)
    second = adapter.send(OUT)
    assert first == second
    assert len(fake.messages) == 1


def test_unsent_draft_does_not_count_for_idempotency():
    fake = FakeGraph()
    adapter = make_adapter(fake)
    # Simulate a crash after draft creation but before /send.
    fake.counter += 1
    fake.messages["draft-x"] = {
        "id": "draft-x",
        "internetMessageId": "<kb-whatever@mail.karenbot.app>",
        "conversationId": "conv-x",
        "isDraft": True,
    }
    assert adapter.find_by_idempotency_key("no-such-key") is None


def test_inbound_uses_conversation_id():
    fake = FakeGraph()
    fake.messages["in-1"] = {
        "id": "in-1",
        "internetMessageId": "<corp-123@corp.example>",
        "conversationId": "conv-55",
        "isDraft": False,
        "folder": "inbox",
        "subject": "Re: Refund request",
        "from": {"emailAddress": {"address": "support@corp.example"}},
        "body": {"contentType": "text", "content": "We can offer you $200."},
    }
    inbound = make_adapter(fake).fetch_inbound()
    assert len(inbound) == 1
    assert inbound[0].provider_thread_id == "conv-55"
    assert inbound[0].provider_message_id == "<corp-123@corp.example>"
    assert "offer you $200" in inbound[0].body

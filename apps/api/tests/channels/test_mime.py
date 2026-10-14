from email import message_from_bytes

from karenbot.channels.base import OutboundMessage
from karenbot.channels.mime_utils import (
    build_mime,
    message_id_for_key,
    parsed_to_inbound,
    thread_root,
)


def make_msg(**overrides) -> OutboundMessage:
    defaults = dict(
        idempotency_key="case:1:action:2",
        recipient_address="support@example.com",
        subject="Refund request",
        body="Please refund $100.",
    )
    defaults.update(overrides)
    return OutboundMessage(**defaults)


def test_message_id_is_deterministic_and_unique_per_key():
    a1 = message_id_for_key("case:1:action:2")
    a2 = message_id_for_key("case:1:action:2")
    b = message_id_for_key("case:1:action:3")
    assert a1 == a2 != b
    assert a1.startswith("<kb-") and a1.endswith("@mail.karenbot.app>")


def test_build_mime_headers_and_threading():
    mime = build_mime(
        make_msg(),
        from_addr="dana@example.com",
        from_name="Dana",
        in_reply_to="<prev@corp.example>",
        references=["<root@corp.example>", "<prev@corp.example>"],
    )
    assert mime["Message-ID"] == message_id_for_key("case:1:action:2")
    assert mime["X-KarenBot-Ref"] == "case:1:action:2"
    assert mime["In-Reply-To"] == "<prev@corp.example>"
    assert "<root@corp.example>" in mime["References"]
    assert mime["To"] == "support@example.com"
    assert "Please refund $100." in mime.get_content()


def test_thread_root_prefers_references_root():
    assert thread_root("<root@x> <mid@x>", "<mid@x>") == "<root@x>"
    assert thread_root(None, "<mid@x>") == "<mid@x>"
    assert thread_root(None, None) is None


def test_parsed_to_inbound_roundtrip():
    mime = build_mime(make_msg(), from_addr="support@corp.example")
    parsed = message_from_bytes(mime.as_bytes())
    inbound = parsed_to_inbound(parsed)
    assert inbound.provider_message_id == message_id_for_key("case:1:action:2")
    assert inbound.subject == "Refund request"
    assert "refund $100" in inbound.body.lower()

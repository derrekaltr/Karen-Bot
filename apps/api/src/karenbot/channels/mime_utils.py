"""Shared MIME construction and threading helpers for email adapters.

Exactly-once across crashes relies on a deterministic Message-ID derived
from the outbox idempotency key: every provider can be searched for it
(Gmail `rfc822msgid:`, Graph `internetMessageId eq`, IMAP `HEADER
Message-ID`), so recovery can always ask "did this already go out?".
"""

import hashlib
from email.message import EmailMessage
from email.utils import formatdate

from karenbot.channels.base import InboundMessage, OutboundMessage

KARENBOT_REF_HEADER = "X-KarenBot-Ref"
MESSAGE_ID_DOMAIN = "mail.karenbot.app"


def message_id_for_key(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode()).hexdigest()[:40]
    return f"<kb-{digest}@{MESSAGE_ID_DOMAIN}>"


def build_mime(
    message: OutboundMessage,
    *,
    from_addr: str,
    from_name: str | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> EmailMessage:
    mime = EmailMessage()
    mime["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    mime["To"] = message.recipient_address
    mime["Subject"] = message.subject or ""
    mime["Date"] = formatdate(localtime=False)
    mime["Message-ID"] = message_id_for_key(message.idempotency_key)
    mime[KARENBOT_REF_HEADER] = message.idempotency_key
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
    if references:
        mime["References"] = " ".join(references)
    mime.set_content(message.body)
    return mime


def thread_root(inbound_references: str | None, in_reply_to: str | None) -> str | None:
    """For IMAP-style threading the conversation key is the root Message-ID:
    the first entry of References, else In-Reply-To."""
    if inbound_references:
        parts = inbound_references.split()
        if parts:
            return parts[0]
    return in_reply_to


def extract_text_body(mime) -> str:
    """Best-effort plain-text extraction from a parsed email.message.Message."""
    if mime.is_multipart():
        for part in mime.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload is not None:
                    return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    payload = mime.get_payload(decode=True)
    if payload is None:
        return str(mime.get_payload() or "")
    return payload.decode(mime.get_content_charset() or "utf-8", "replace")


def parsed_to_inbound(mime, *, provider_message_id: str | None = None) -> InboundMessage:
    """Convert a parsed RFC822 message into the channel-neutral shape."""
    msg_id = provider_message_id or (mime.get("Message-ID") or "").strip()
    return InboundMessage(
        provider_message_id=msg_id,
        provider_thread_id=thread_root(mime.get("References"), mime.get("In-Reply-To")),
        from_address=mime.get("From", ""),
        subject=mime.get("Subject"),
        body=extract_text_body(mime),
        metadata={"in_reply_to": mime.get("In-Reply-To")},
    )

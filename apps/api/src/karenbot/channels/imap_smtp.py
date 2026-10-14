"""Generic IMAP/SMTP adapter: Yahoo, iCloud, Fastmail, custom domains.

Credentials are app passwords (or XOAUTH2 later) stored encrypted on the
connected account. Idempotency: after SMTP send we APPEND the message to the
IMAP Sent folder, so find_by_idempotency_key can search
`HEADER Message-ID <deterministic-id>` there. Threading uses standard
In-Reply-To/References headers with the root Message-ID as the thread key.

Factories for the SMTP/IMAP clients are injectable for tests.
"""

import imaplib
import smtplib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email import message_from_bytes

from karenbot.channels.base import InboundMessage, OutboundMessage, SendReceipt
from karenbot.channels.mime_utils import build_mime, message_id_for_key, parsed_to_inbound
from karenbot.domain.enums import Channel


@dataclass(frozen=True)
class ImapSmtpConfig:
    email: str
    smtp_host: str
    imap_host: str
    username: str
    password: str
    smtp_port: int = 587
    imap_port: int = 993
    sent_folder: str = "Sent"


def _default_smtp(config: ImapSmtpConfig) -> smtplib.SMTP:
    client = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
    client.starttls()
    client.login(config.username, config.password)
    return client


def _default_imap(config: ImapSmtpConfig) -> imaplib.IMAP4:
    client = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
    client.login(config.username, config.password)
    return client


class ImapSmtpAdapter:
    channel = Channel.EMAIL

    def __init__(
        self,
        config: ImapSmtpConfig,
        smtp_factory: Callable[[ImapSmtpConfig], smtplib.SMTP] | None = None,
        imap_factory: Callable[[ImapSmtpConfig], imaplib.IMAP4] | None = None,
    ):
        self.config = config
        self.smtp_factory = smtp_factory or _default_smtp
        self.imap_factory = imap_factory or _default_imap

    def send(self, message: OutboundMessage) -> SendReceipt:
        existing = self.find_by_idempotency_key(message.idempotency_key)
        if existing is not None:
            return existing
        mime = build_mime(
            message,
            from_addr=self.config.email,
            in_reply_to=message.metadata.get("in_reply_to"),
            references=message.metadata.get("references"),
        )
        message_id = message_id_for_key(message.idempotency_key)
        smtp = self.smtp_factory(self.config)
        try:
            smtp.send_message(mime)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        # Record in Sent via IMAP so idempotency search works after a crash.
        imap = self.imap_factory(self.config)
        try:
            imap.append(
                self.config.sent_folder,
                "(\\Seen)",
                imaplib.Time2Internaldate(time.time()),
                mime.as_bytes(),
            )
        finally:
            try:
                imap.logout()
            except Exception:
                pass
        return SendReceipt(
            provider_message_id=message_id,
            provider_thread_id=message.thread_provider_id or message_id,
        )

    def find_by_idempotency_key(self, key: str) -> SendReceipt | None:
        message_id = message_id_for_key(key)
        imap = self.imap_factory(self.config)
        try:
            status, _ = imap.select(self.config.sent_folder, readonly=True)
            if status != "OK":
                return None
            status, data = imap.search(None, "HEADER", "Message-ID", message_id)
            if status == "OK" and data and data[0].split():
                return SendReceipt(
                    provider_message_id=message_id, provider_thread_id=message_id
                )
            return None
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def fetch_inbound(self, since: datetime | None = None) -> list[InboundMessage]:
        imap = self.imap_factory(self.config)
        results: list[InboundMessage] = []
        try:
            status, _ = imap.select("INBOX", readonly=True)
            if status != "OK":
                return []
            criteria: list[str] = ["ALL"] if since is None else [
                "SINCE",
                since.astimezone(UTC).strftime("%d-%b-%Y"),
            ]
            status, data = imap.search(None, *criteria)
            if status != "OK" or not data:
                return []
            for num in data[0].split()[-25:]:
                status, fetched = imap.fetch(num, "(RFC822)")
                if status != "OK" or not fetched or fetched[0] is None:
                    continue
                raw = fetched[0][1]
                if not isinstance(raw, (bytes, bytearray)):
                    continue
                mime = message_from_bytes(bytes(raw))
                inbound = parsed_to_inbound(mime)
                results.append(
                    InboundMessage(
                        provider_message_id=inbound.provider_message_id,
                        # Thread key: root of References, else the message
                        # being replied to, else itself (new thread).
                        provider_thread_id=inbound.provider_thread_id
                        or inbound.metadata.get("in_reply_to")
                        or inbound.provider_message_id,
                        from_address=inbound.from_address,
                        subject=inbound.subject,
                        body=inbound.body,
                        received_at=datetime.now(UTC),
                        metadata=inbound.metadata,
                    )
                )
            return results
        finally:
            try:
                imap.logout()
            except Exception:
                pass

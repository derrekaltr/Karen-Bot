"""Channel abstraction: email now, chat and voice later.

Every adapter speaks the same protocol; every message in either direction on
any channel becomes a `communications` row. Voice will implement `send()` as
"place a call with pre-approved talking points" and return transcripts as
inbound messages.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from karenbot.domain.enums import Channel


@dataclass(frozen=True)
class OutboundMessage:
    idempotency_key: str
    recipient_address: str
    body: str
    subject: str | None = None
    thread_provider_id: str | None = None  # continue an existing provider thread
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendReceipt:
    provider_message_id: str
    provider_thread_id: str


@dataclass(frozen=True)
class InboundMessage:
    provider_message_id: str
    provider_thread_id: str | None
    from_address: str
    body: str
    subject: str | None = None
    received_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter(Protocol):
    channel: Channel

    def send(self, message: OutboundMessage) -> SendReceipt:
        """Deliver a message. Must be safe to retry with the same idempotency key."""
        ...

    def fetch_inbound(self, since: datetime | None = None) -> list[InboundMessage]:
        """Return new inbound messages (poll-based adapters)."""
        ...

    def find_by_idempotency_key(self, key: str) -> SendReceipt | None:
        """Crash recovery: did a message with this key already go out?"""
        ...

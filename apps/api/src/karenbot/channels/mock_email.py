"""In-process email adapter for development, tests, and the e2e demo.

A pluggable responder (see karenbot.simulator) decides how the "company"
replies to each sent message. Sent mail is kept indexed by idempotency key so
crash-recovery paths can be exercised realistically.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from karenbot.channels.base import InboundMessage, OutboundMessage, SendReceipt
from karenbot.domain.enums import Channel

Responder = Callable[[OutboundMessage, int], list[InboundMessage]]


class MockEmailAdapter:
    channel = Channel.EMAIL

    def __init__(self, responder: Responder | None = None):
        self.responder = responder
        self.sent: list[OutboundMessage] = []
        self._receipts_by_key: dict[str, SendReceipt] = {}
        self._inbound_queue: list[InboundMessage] = []
        self._threads: dict[str, str] = {}  # recipient -> thread id
        self.fail_next_send = False  # test hook

    def send(self, message: OutboundMessage) -> SendReceipt:
        if self.fail_next_send:
            self.fail_next_send = False
            raise ConnectionError("simulated provider outage")
        # Provider-side idempotency: same key returns the original receipt.
        if message.idempotency_key in self._receipts_by_key:
            return self._receipts_by_key[message.idempotency_key]

        thread_id = message.thread_provider_id or self._threads.setdefault(
            message.recipient_address, f"thread-{uuid.uuid4().hex[:8]}"
        )
        receipt = SendReceipt(
            provider_message_id=f"msg-{uuid.uuid4().hex[:12]}",
            provider_thread_id=thread_id,
        )
        self.sent.append(message)
        self._receipts_by_key[message.idempotency_key] = receipt

        if self.responder is not None:
            exchange_index = sum(
                1 for m in self.sent if m.recipient_address == message.recipient_address
            )
            for reply in self.responder(message, exchange_index):
                self._inbound_queue.append(
                    InboundMessage(
                        provider_message_id=reply.provider_message_id,
                        provider_thread_id=reply.provider_thread_id or thread_id,
                        from_address=reply.from_address,
                        subject=reply.subject,
                        body=reply.body,
                        received_at=reply.received_at or datetime.now(UTC),
                        metadata=reply.metadata,
                    )
                )
        return receipt

    def fetch_inbound(self, since: datetime | None = None) -> list[InboundMessage]:
        messages, self._inbound_queue = self._inbound_queue, []
        return messages

    def find_by_idempotency_key(self, key: str) -> SendReceipt | None:
        return self._receipts_by_key.get(key)

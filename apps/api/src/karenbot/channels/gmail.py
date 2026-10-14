"""Gmail adapter (Gmail REST API over httpx; no Google SDK).

- send: users.messages.send with raw MIME; thread continuity via threadId +
  In-Reply-To/References headers.
- idempotency: deterministic Message-ID; find_by_idempotency_key searches
  `rfc822msgid:` which Gmail indexes natively.
- inbound: users.messages.list on the inbox, newest since the given time.
"""

import base64
from collections.abc import Callable
from datetime import UTC, datetime
from email import message_from_bytes

import httpx

from karenbot.channels.base import InboundMessage, OutboundMessage, SendReceipt
from karenbot.channels.mime_utils import build_mime, message_id_for_key, parsed_to_inbound
from karenbot.domain.enums import Channel

API = "https://gmail.googleapis.com/gmail/v1/users/me"

# Returns a currently-valid access token (refreshing if needed).
TokenGetter = Callable[[], str]


class GmailAdapter:
    channel = Channel.EMAIL

    def __init__(
        self,
        token_getter: TokenGetter,
        from_addr: str,
        http: httpx.Client | None = None,
    ):
        self.token_getter = token_getter
        self.from_addr = from_addr
        self.http = http or httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_getter()}"}

    def send(self, message: OutboundMessage) -> SendReceipt:
        existing = self.find_by_idempotency_key(message.idempotency_key)
        if existing is not None:
            return existing
        in_reply_to = message.metadata.get("in_reply_to")
        references = message.metadata.get("references")
        mime = build_mime(
            message,
            from_addr=self.from_addr,
            in_reply_to=in_reply_to,
            references=references,
        )
        payload: dict = {
            "raw": base64.urlsafe_b64encode(mime.as_bytes()).decode()
        }
        if message.thread_provider_id:
            payload["threadId"] = message.thread_provider_id
        response = self.http.post(
            f"{API}/messages/send", json=payload, headers=self._headers()
        )
        response.raise_for_status()
        data = response.json()
        return SendReceipt(
            provider_message_id=data["id"], provider_thread_id=data["threadId"]
        )

    def find_by_idempotency_key(self, key: str) -> SendReceipt | None:
        rfc_id = message_id_for_key(key).strip("<>")
        response = self.http.get(
            f"{API}/messages",
            params={"q": f"rfc822msgid:{rfc_id}", "maxResults": 1},
            headers=self._headers(),
        )
        response.raise_for_status()
        messages = response.json().get("messages") or []
        if not messages:
            return None
        return SendReceipt(
            provider_message_id=messages[0]["id"],
            provider_thread_id=messages[0].get("threadId", ""),
        )

    def fetch_inbound(self, since: datetime | None = None) -> list[InboundMessage]:
        query = "in:inbox"
        if since is not None:
            query += f" after:{int(since.astimezone(UTC).timestamp())}"
        response = self.http.get(
            f"{API}/messages",
            params={"q": query, "maxResults": 25},
            headers=self._headers(),
        )
        response.raise_for_status()
        results: list[InboundMessage] = []
        for stub in response.json().get("messages") or []:
            detail = self.http.get(
                f"{API}/messages/{stub['id']}",
                params={"format": "raw"},
                headers=self._headers(),
            )
            detail.raise_for_status()
            data = detail.json()
            mime = message_from_bytes(base64.urlsafe_b64decode(data["raw"]))
            inbound = parsed_to_inbound(mime, provider_message_id=data["id"])
            results.append(
                InboundMessage(
                    provider_message_id=inbound.provider_message_id,
                    # Gmail has first-class threads; prefer them over header
                    # reconstruction.
                    provider_thread_id=data.get("threadId") or inbound.provider_thread_id,
                    from_address=inbound.from_address,
                    subject=inbound.subject,
                    body=inbound.body,
                    received_at=datetime.now(UTC),
                    metadata=inbound.metadata,
                )
            )
        return results

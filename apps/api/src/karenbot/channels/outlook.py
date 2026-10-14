"""Outlook / Microsoft 365 adapter (Microsoft Graph over httpx).

- send: create a draft message carrying our deterministic internetMessageId,
  then POST /send — this (unlike /sendMail) yields the message id and
  conversationId for threading.
- idempotency: find_by_idempotency_key filters sent items on
  internetMessageId.
- inbound: inbox messages filtered by receivedDateTime; threading via
  conversationId.
"""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from karenbot.channels.base import InboundMessage, OutboundMessage, SendReceipt
from karenbot.channels.mime_utils import message_id_for_key
from karenbot.domain.enums import Channel

API = "https://graph.microsoft.com/v1.0/me"

TokenGetter = Callable[[], str]


class OutlookAdapter:
    channel = Channel.EMAIL

    def __init__(self, token_getter: TokenGetter, http: httpx.Client | None = None):
        self.token_getter = token_getter
        self.http = http or httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_getter()}"}

    def send(self, message: OutboundMessage) -> SendReceipt:
        existing = self.find_by_idempotency_key(message.idempotency_key)
        if existing is not None:
            return existing
        draft_payload = {
            "subject": message.subject or "",
            "body": {"contentType": "text", "content": message.body},
            "toRecipients": [
                {"emailAddress": {"address": message.recipient_address}}
            ],
            "internetMessageId": message_id_for_key(message.idempotency_key),
        }
        draft = self.http.post(
            f"{API}/messages", json=draft_payload, headers=self._headers()
        )
        draft.raise_for_status()
        data = draft.json()
        sent = self.http.post(
            f"{API}/messages/{data['id']}/send", headers=self._headers()
        )
        sent.raise_for_status()
        return SendReceipt(
            provider_message_id=data["internetMessageId"],
            provider_thread_id=data.get("conversationId", ""),
        )

    def find_by_idempotency_key(self, key: str) -> SendReceipt | None:
        rfc_id = message_id_for_key(key)
        response = self.http.get(
            f"{API}/messages",
            params={
                "$filter": f"internetMessageId eq '{rfc_id}'",
                "$select": "id,internetMessageId,conversationId,isDraft",
                "$top": "5",
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        for item in response.json().get("value", []):
            if not item.get("isDraft"):
                return SendReceipt(
                    provider_message_id=item["internetMessageId"],
                    provider_thread_id=item.get("conversationId", ""),
                )
        return None

    def fetch_inbound(self, since: datetime | None = None) -> list[InboundMessage]:
        params: dict[str, str] = {
            "$select": "id,internetMessageId,conversationId,subject,from,receivedDateTime,body,bodyPreview",
            "$orderby": "receivedDateTime desc",
            "$top": "25",
        }
        if since is not None:
            iso = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            params["$filter"] = f"receivedDateTime ge {iso}"
        response = self.http.get(
            f"{API}/mailFolders/inbox/messages", params=params, headers=self._headers()
        )
        response.raise_for_status()
        results: list[InboundMessage] = []
        for item in response.json().get("value", []):
            body = item.get("body") or {}
            content = body.get("content", "") or item.get("bodyPreview", "")
            results.append(
                InboundMessage(
                    provider_message_id=item.get("internetMessageId") or item["id"],
                    provider_thread_id=item.get("conversationId"),
                    from_address=(item.get("from") or {})
                    .get("emailAddress", {})
                    .get("address", ""),
                    subject=item.get("subject"),
                    body=content,
                    received_at=datetime.now(UTC),
                    metadata={"graph_id": item["id"]},
                )
            )
        return results

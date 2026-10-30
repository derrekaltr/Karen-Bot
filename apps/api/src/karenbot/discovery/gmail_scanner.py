"""Live Gmail inbox scanner: real mailbox search for claims and evidence.

v1 is deliberately heuristic — targeted Gmail search queries plus light
parsing (sender display name, dollar amounts in snippets). High precision
over recall: surface things that are very likely claimable and let the
user decide. LLM-powered extraction (reading full bodies, computing
amounts, matching to policies) lands once the Anthropic account has
credits; the scanner interface doesn't change.

Only ever runs user-initiated over the user's own connected mailbox with
gmail.readonly consent; results are shown to the user, never acted on
automatically.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.utils import parseaddr
from typing import TYPE_CHECKING

import httpx

from karenbot.discovery.inbox_scan import ClaimCandidate, EvidenceHit

if TYPE_CHECKING:
    from karenbot.discovery.plaid import RecurringStream

API = "https://gmail.googleapis.com/gmail/v1/users/me"

AMOUNT_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")

# (gmail query, kind, industry, suggested_category) — precision-first.
CLAIM_QUERIES: list[tuple[str, str, str, str]] = [
    (
        'subject:(cancelled OR canceled OR cancellation) (flight OR trip) newer_than:1y',
        "cancelled_flight",
        "airline",
        "flight_cancellation_refund",
    ),
    (
        "subject:(delayed OR delay) (flight OR trip) newer_than:1y",
        "flight_delay",
        "airline",
        "flight_delay_compensation",
    ),
    (
        '"trip credit" OR "flight credit" OR "travel credit" OR "travel voucher" newer_than:1y',
        "unused_flight_credit",
        "airline",
        "flight_credit_reissue",
    ),
    (
        'subject:("not delivered" OR "couldn\'t deliver" OR "delivery problem" OR "wasn\'t delivered") newer_than:6m',
        "failed_delivery",
        "ecommerce",
        "undelivered_item",
    ),
    (
        'subject:(refund) ("not processed" OR pending OR delayed) newer_than:6m',
        "missing_refund",
        "ecommerce",
        "missing_refund",
    ),
]

MAX_PER_QUERY = 4


@dataclass
class _Message:
    id: str
    thread_id: str
    subject: str
    sender_name: str
    sender_address: str
    snippet: str
    received_at: datetime


class GmailInboxScanner:
    def __init__(self, token_getter: Callable[[], str], http: httpx.Client | None = None):
        self.token_getter = token_getter
        self.http = http or httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_getter()}"}

    def _search(self, query: str, max_results: int) -> list[_Message]:
        response = self.http.get(
            f"{API}/messages",
            params={"q": query, "maxResults": max_results},
            headers=self._headers(),
        )
        response.raise_for_status()
        results: list[_Message] = []
        for stub in response.json().get("messages", []) or []:
            detail = self.http.get(
                f"{API}/messages/{stub['id']}",
                params={
                    "format": "metadata",
                    "metadataHeaders": ["Subject", "From", "Date"],
                },
                headers=self._headers(),
            )
            if detail.status_code != 200:
                continue
            data = detail.json()
            headers = {
                h["name"].lower(): h["value"]
                for h in data.get("payload", {}).get("headers", [])
            }
            name, address = parseaddr(headers.get("from", ""))
            received = datetime.fromtimestamp(
                int(data.get("internalDate", "0")) / 1000, UTC
            )
            results.append(
                _Message(
                    id=data["id"],
                    thread_id=data.get("threadId", data["id"]),
                    subject=headers.get("subject", "(no subject)"),
                    sender_name=name or address.split("@")[0],
                    sender_address=address,
                    snippet=data.get("snippet", ""),
                    received_at=received,
                )
            )
        return results

    # ---- InboxScanner protocol ------------------------------------------

    def scan_claims(self) -> list[ClaimCandidate]:
        candidates: list[ClaimCandidate] = []
        seen_threads: set[str] = set()
        for query, kind, industry, category in CLAIM_QUERIES:
            try:
                messages = self._search(query, MAX_PER_QUERY)
            except httpx.HTTPError:
                continue  # one failing query must not kill the scan
            for message in messages:
                if message.thread_id in seen_threads:
                    continue
                seen_threads.add(message.thread_id)
                amount_match = AMOUNT_RE.search(message.snippet)
                amount = (
                    Decimal(amount_match.group(1).replace(",", ""))
                    if amount_match
                    else None
                )
                candidates.append(
                    ClaimCandidate(
                        kind=kind,
                        company_name=message.sender_name,
                        company_industry=industry,
                        suggested_category=category,
                        title=message.subject,
                        snippet=message.snippet[:280],
                        amount=amount,
                        occurred_at=message.received_at,
                        reference=f"gmail:{message.id}",
                    )
                )
        candidates.sort(key=lambda c: c.occurred_at, reverse=True)
        return candidates

    def list_senders(self) -> list[str]:
        """Recent sender addresses (user-initiated company discovery).

        Bills and receipts are what identify a vendor relationship, so the
        query leans on billing vocabulary rather than reading everything.
        """
        senders: set[str] = set()
        for query in (
            "newer_than:180d (bill OR statement OR receipt OR invoice)",
            "newer_than:180d (reservation OR itinerary OR confirmation)",
        ):
            try:
                for message in self._search(query, 40):
                    if message.sender_address:
                        senders.add(message.sender_address.lower())
            except httpx.HTTPError:
                continue
        return sorted(senders)

    def find_recurring_receipts(self) -> list["RecurringStream"]:
        """Infer recurring charges from billing receipts in the mailbox.

        Heuristic v1: group receipt-like messages by sender domain label,
        keep groups with 2+ messages whose snippets carry a stable dollar
        amount, and classify cadence from the median gap between messages.
        """
        from statistics import median

        from karenbot.discovery.company_profile import sender_label
        from karenbot.discovery.plaid import RecurringStream

        seen_ids: set[str] = set()
        messages: list[_Message] = []
        for query in (
            'newer_than:210d subject:(receipt OR invoice OR "payment confirmation" OR renewal)',
            'newer_than:210d ("your receipt" OR "payment received" OR "subscription renew")',
        ):
            try:
                for message in self._search(query, 60):
                    if message.id not in seen_ids:
                        seen_ids.add(message.id)
                        messages.append(message)
            except httpx.HTTPError:
                continue

        groups: dict[str, list[_Message]] = {}
        for message in messages:
            label = sender_label(message.sender_address)
            if label:
                groups.setdefault(label, []).append(message)

        streams: list[RecurringStream] = []
        for group in groups.values():
            if len(group) < 2:
                continue
            amounts = []
            for message in group:
                m = AMOUNT_RE.search(message.snippet) or AMOUNT_RE.search(message.subject)
                if m:
                    amounts.append(Decimal(m.group(1).replace(",", "")))
            if not amounts:
                continue
            # Stable amount: the most frequent one in the group.
            amount = max(set(amounts), key=amounts.count)
            dates = sorted(m.received_at for m in group)
            gaps = [
                (b - a).days for a, b in zip(dates, dates[1:], strict=False) if (b - a).days > 0
            ]
            if not gaps:
                continue
            gap = median(gaps)
            if 5 <= gap <= 9:
                cadence = "weekly"
            elif 21 <= gap <= 45:
                cadence = "monthly"
            elif 300 <= gap <= 430:
                cadence = "yearly"
            else:
                continue  # irregular: not a subscription we can assert
            sender_names = [m.sender_name for m in group if m.sender_name]
            merchant = max(set(sender_names), key=sender_names.count) if sender_names else "Unknown"
            streams.append(
                RecurringStream(
                    merchant_name=merchant,
                    amount=amount,
                    currency="USD",
                    cadence=cadence,
                    first_date=dates[0],
                    last_date=dates[-1],
                    occurrences=len(group),
                )
            )
        return streams

    def find_evidence(self, company_name: str, keywords: list[str]) -> list[EvidenceHit]:
        # Company name exact-phrase plus the most distinctive claim keyword.
        distinctive = [k for k in keywords if len(k) > 4][:2]
        query = f'"{company_name}" newer_than:1y'
        hits: list[EvidenceHit] = []
        try:
            messages = self._search(query, 8)
        except httpx.HTTPError:
            return []
        cutoff = datetime.now(UTC) - timedelta(days=400)
        for message in messages:
            if message.received_at < cutoff:
                continue
            hits.append(
                EvidenceHit(
                    summary=(
                        f"Email: {message.subject} "
                        f"(from {message.sender_name}, {message.received_at:%b %d, %Y})"
                    ),
                    snippet=message.snippet[:280],
                    occurred_at=message.received_at,
                    reference=f"gmail:{message.id}",
                )
            )
        # Prefer messages matching claim keywords, then recency.
        def keyword_rank(hit: EvidenceHit) -> int:
            text = f"{hit.summary} {hit.snippet}".lower()
            return sum(1 for k in distinctive if k.lower() in text)

        hits.sort(key=lambda h: (keyword_rank(h), h.occurred_at), reverse=True)
        return hits[:6]

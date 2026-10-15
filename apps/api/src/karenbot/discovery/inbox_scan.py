"""Inbox scanning: find claimable situations and case evidence in email.

Two operations:
- scan_claims(): sweep the mailbox for things worth pursuing (unflown
  flights with unused credits, cancelled flights, failed deliveries,
  duplicate charges) and return candidates the user can turn into cases
  with one click.
- find_evidence(company, keywords): locate messages relevant to an open
  case (itineraries, receipts, support threads) to attach as evidence.

Scanning only ever runs over the user's OWN connected mailbox with their
authorization (user-initiated button, not background surveillance). Real
provider implementations use mailbox search (Gmail `q=`, Graph `$search`,
IMAP SEARCH) over the connected account; dev uses the mock below.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from karenbot.config import get_settings


@dataclass(frozen=True)
class ClaimCandidate:
    kind: str  # unused_flight_credit | cancelled_flight | failed_delivery | duplicate_charge
    company_name: str
    company_industry: str
    suggested_category: str
    title: str
    snippet: str
    amount: Decimal | None
    occurred_at: datetime
    reference: str  # provider message id


@dataclass(frozen=True)
class EvidenceHit:
    summary: str
    snippet: str
    occurred_at: datetime
    reference: str


class InboxScanner(Protocol):
    def scan_claims(self) -> list[ClaimCandidate]: ...

    def find_evidence(self, company_name: str, keywords: list[str]) -> list[EvidenceHit]: ...


@dataclass
class MockInboxScanner:
    """Dev/test scanner: a plausible inbox's worth of claimable situations."""

    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _candidates(self) -> list[ClaimCandidate]:
        return [
            ClaimCandidate(
                kind="unused_flight_credit",
                company_name="American Airlines",
                company_industry="airline",
                suggested_category="flight_credit_reissue",
                title="$840 in unused flight credits",
                snippet="Your trip credit from confirmation JXK42L is scheduled to "
                "expire. Original ticket value: $840.00 (2 unflown segments).",
                amount=Decimal("840.00"),
                occurred_at=self.now - timedelta(days=12),
                reference="scan-aa-credit-1",
            ),
            ClaimCandidate(
                kind="cancelled_flight",
                company_name="Delta Air Lines",
                company_industry="airline",
                suggested_category="flight_cancellation_refund",
                title="Cancelled flight DL 2214 — refund not received",
                snippet="We're sorry — flight DL 2214 on May 3 was cancelled. "
                "Fare paid: $412.60. No refund confirmation found in inbox.",
                amount=Decimal("412.60"),
                occurred_at=self.now - timedelta(days=40),
                reference="scan-dl-cancel-1",
            ),
            ClaimCandidate(
                kind="failed_delivery",
                company_name="Amazon",
                company_industry="ecommerce",
                suggested_category="undelivered_item",
                title="Order never delivered",
                snippet="Order #114-2958 ($67.49) marked 'delivered' but a "
                "follow-up thread shows you reported it missing with no refund.",
                amount=Decimal("67.49"),
                occurred_at=self.now - timedelta(days=9),
                reference="scan-amz-delivery-1",
            ),
            ClaimCandidate(
                kind="duplicate_charge",
                company_name="Uber",
                company_industry="rideshare",
                suggested_category="incorrect_charge",
                title="Possible duplicate trip charge",
                snippet="Two receipts for the same route and timestamp on Jun 2: "
                "$23.80 and $23.80.",
                amount=Decimal("23.80"),
                occurred_at=self.now - timedelta(days=5),
                reference="scan-uber-dupe-1",
            ),
        ]

    def scan_claims(self) -> list[ClaimCandidate]:
        return self._candidates()

    def find_evidence(self, company_name: str, keywords: list[str]) -> list[EvidenceHit]:
        needle = company_name.lower().split()[0]
        hits: list[EvidenceHit] = []
        for candidate in self._candidates():
            if needle in candidate.company_name.lower():
                hits.append(
                    EvidenceHit(
                        summary=f"Email: {candidate.title}",
                        snippet=candidate.snippet,
                        occurred_at=candidate.occurred_at,
                        reference=candidate.reference,
                    )
                )
        # Generic receipts that match claim keywords.
        if any("baggage" in k or "expense" in k for k in keywords):
            hits.append(
                EvidenceHit(
                    summary="Email: purchase receipts during baggage delay",
                    snippet="Receipts found: pharmacy $42.10, clothing $187.90.",
                    occurred_at=self.now - timedelta(days=20),
                    reference="scan-receipts-1",
                )
            )
        return hits


def get_inbox_scanner(session=None, user=None) -> InboxScanner:
    """Live scanner when the user has a connected Gmail account; the mock
    demo inbox otherwise (dev mode only)."""
    if session is not None and user is not None:
        from sqlalchemy import select

        from karenbot.channels.resolver import _token_getter
        from karenbot.discovery.gmail_scanner import GmailInboxScanner
        from karenbot.domain.models import ConnectedAccount

        account = session.scalars(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.provider == "gmail",
                ConnectedAccount.status == "active",
                ConnectedAccount.revoked_at.is_(None),
            )
        ).first()
        if account is not None and account.encrypted_token_reference:
            return GmailInboxScanner(_token_getter(account.id, "gmail"))

    settings = get_settings()
    if settings.email_provider == "mock" or settings.dev_mode:
        return MockInboxScanner()
    raise NotImplementedError(
        "inbox scanning requires a connected email account"
    )

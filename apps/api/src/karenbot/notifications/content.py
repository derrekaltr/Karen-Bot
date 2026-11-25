"""What Karen says on the lock screen, and when.

Notifications fire only for case events that happen while the customer
isn't looking — company replies and follow-up timers processed by the
worker. Anything a customer causes from the app (signing, approving,
confirming the money landed) is deliberately absent: they are already
watching it happen, and some of those run under the agent actor (e.g.
"I received the money" executes a CloseCase action), so actor type alone
can't tell them apart. Keep this an explicit allowlist.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.domain.enums import ActorType, CaseEvent, CaseStatus
from karenbot.domain.models import Case, Company, RecoveryOutcome


@dataclass(frozen=True)
class PushContent:
    title: str
    body: str
    # "high" wakes the phone promptly; reserved for "Karen needs you".
    priority: str = "default"
    data: dict[str, Any] = field(default_factory=dict)


SUBSCRIPTION_CANCELLATION = "subscription_cancellation"


def _company_name(session: Session, case: Case) -> str:
    if case.company_id is not None:
        company = session.get(Company, case.company_id)
        if company is not None:
            return company.name
    return "The company"


def _latest_offer(session: Session, case: Case) -> RecoveryOutcome | None:
    return session.scalars(
        select(RecoveryOutcome)
        .where(RecoveryOutcome.case_id == case.id)
        .order_by(RecoveryOutcome.created_at.desc())
    ).first()


def format_money(amount: Decimal | None, currency: str) -> str | None:
    if amount is None:
        return None
    if currency.upper() == "USD":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency.upper()}"


def content_for_transition(
    session: Session,
    case: Case,
    event: CaseEvent,
    *,
    actor_type: ActorType,
    to_status: CaseStatus,
) -> PushContent | None:
    """The notification for this transition, or None if it shouldn't ping."""
    if actor_type == ActorType.CUSTOMER:
        return None  # defensive: never notify people about their own taps

    company = _company_name(session, case)
    data = {"case_id": str(case.id), "event": event.value}
    cancellation = case.category == SUBSCRIPTION_CANCELLATION

    if event == CaseEvent.APPROVAL_REQUESTED:
        offer = _latest_offer(session, case)
        amount = format_money(offer.amount, offer.currency) if offer else None
        if cancellation:
            return PushContent(
                title=f"{company} is trying to keep you",
                body="They made a retention offer. Take it, or Karen keeps canceling.",
                priority="high",
                data=data,
            )
        return PushContent(
            title=f"{company} offered {amount}" if amount else f"{company} made an offer",
            body="Karen won't accept anything binding without you. Tap to take it "
            "or send her back in.",
            priority="high",
            data=data,
        )

    if event == CaseEvent.CANCELLATION_CONFIRMED:
        return PushContent(
            title=f"{company} confirmed your cancellation",
            body="Check that the billing actually stops, then let Karen know.",
            data=data,
        )

    if event == CaseEvent.ESCALATION_STARTED:
        return PushContent(
            title=f"Karen is escalating with {company}",
            body="Front-line support stalled, so she's going over their heads.",
            data=data,
        )

    if event == CaseEvent.NO_RESPONSE_EXHAUSTED:
        if to_status == CaseStatus.ESCALATED:
            return PushContent(
                title=f"{company} went quiet",
                body="No reply after repeated follow-ups. Karen is escalating.",
                data=data,
            )
        if to_status == CaseStatus.CLOSED_UNSUCCESSFUL:
            return PushContent(
                title=f"Karen closed your {company} case",
                body="She couldn't get this one over the line. Tap for the full paper trail.",
                data=data,
            )

    return None

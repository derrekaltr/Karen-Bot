"""CaseContext: the deterministic snapshot the policy engine evaluates against.

Built from the database by `build_case_context`; the policy engine itself is
pure and does no I/O.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.config import get_settings
from karenbot.domain.enums import Direction, OutboxStatus
from karenbot.domain.fingerprint import message_fingerprint
from karenbot.domain.models import (
    Case,
    CaseAuthorization,
    CaseEvidence,
    Communication,
    Company,
    OutboxMessage,
    SupportChannel,
)


@dataclass(frozen=True)
class AuthorizationSnapshot:
    active: bool
    authorized_actions: frozenset[str]
    prohibited_actions: frozenset[str]
    authorized_claim_types: frozenset[str]
    max_requested_amount: Decimal | None


@dataclass(frozen=True)
class CaseContext:
    case_id: uuid.UUID
    case_status: str
    # Moral code: the company's size class and whether it may be targeted at
    # all. Small businesses and unclassified companies are never targetable.
    company_size_class: str
    company_targetable: bool
    # Respect-the-refusal: the company has said it only deals with customers
    # directly. Agent-sent messages are denied; draft_for_customer remains.
    company_refuses_third_party: bool
    authorization: AuthorizationSnapshot | None
    verified_support_channel_ids: frozenset[uuid.UUID]
    evidence_ids: frozenset[uuid.UUID]
    outbound_count_24h: int
    outbound_count_total: int
    follow_ups_sent: int
    last_outbound_at: datetime | None
    recent_outbound_fingerprints: frozenset[str]
    pending_outbox_fingerprints: frozenset[str] = field(default_factory=frozenset)
    kill_switch_active: bool = False
    # Global limits (from settings, overridable for tests)
    max_outbound_per_day: int = 3
    max_outbound_total: int = 12
    max_follow_ups: int = 4
    min_hours_between_outbound: int = 20


def build_case_context(session: Session, case: Case) -> CaseContext:
    settings = get_settings()
    now = datetime.now(UTC)

    company = session.get(Company, case.company_id)
    size_class = company.size_class if company else "unclassified"
    targetable = size_class in settings.targetable_size_classes
    refuses_third_party = bool(company.refuses_third_party) if company else False

    auth_row = session.scalars(
        select(CaseAuthorization)
        .where(CaseAuthorization.case_id == case.id, CaseAuthorization.revoked_at.is_(None))
        .order_by(CaseAuthorization.consent_timestamp.desc())
    ).first()
    authorization = None
    if auth_row is not None:
        authorization = AuthorizationSnapshot(
            active=True,
            authorized_actions=frozenset(auth_row.authorized_actions),
            prohibited_actions=frozenset(auth_row.prohibited_actions),
            authorized_claim_types=frozenset(auth_row.authorized_claim_types),
            max_requested_amount=auth_row.max_requested_amount,
        )

    channel_ids = frozenset(
        session.scalars(
            select(SupportChannel.id).where(
                SupportChannel.company_id == case.company_id,
                SupportChannel.verified.is_(True),
                SupportChannel.active.is_(True),
            )
        ).all()
    )

    evidence_ids = frozenset(
        session.scalars(select(CaseEvidence.id).where(CaseEvidence.case_id == case.id)).all()
    )

    outbound_q = select(Communication).where(
        Communication.case_id == case.id,
        Communication.direction == Direction.OUTBOUND.value,
        Communication.counterparty == "company",
    )
    outbound = session.scalars(outbound_q).all()
    cutoff = now - timedelta(hours=24)

    def _aware(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    sent_times = [t for c in outbound if (t := _aware(c.sent_at)) is not None]
    outbound_count_24h = sum(1 for t in sent_times if t >= cutoff)
    last_outbound_at = max(sent_times) if sent_times else None

    follow_ups_sent = sum(1 for c in outbound if (c.classification or {}).get("is_follow_up"))

    # Fingerprints of recent sends and not-yet-sent queued messages, for
    # duplicate detection.
    recent_fps = {message_fingerprint(c.subject, c.body) for c in outbound}
    pending = session.scalars(
        select(OutboxMessage).where(
            OutboxMessage.case_id == case.id,
            OutboxMessage.status.in_([OutboxStatus.PENDING.value, OutboxStatus.SENDING.value]),
        )
    ).all()
    pending_fps = {message_fingerprint(m.subject, m.body) for m in pending}

    return CaseContext(
        case_id=case.id,
        case_status=case.status,
        company_size_class=size_class,
        company_targetable=targetable,
        company_refuses_third_party=refuses_third_party,
        authorization=authorization,
        verified_support_channel_ids=channel_ids,
        evidence_ids=evidence_ids,
        outbound_count_24h=outbound_count_24h,
        outbound_count_total=len(outbound),
        follow_ups_sent=int(follow_ups_sent),
        last_outbound_at=last_outbound_at,
        recent_outbound_fingerprints=frozenset(recent_fps),
        pending_outbox_fingerprints=frozenset(pending_fps),
        kill_switch_active=False,
        max_outbound_per_day=settings.max_outbound_per_case_per_day,
        max_outbound_total=settings.max_outbound_per_case_total,
        max_follow_ups=settings.max_follow_ups,
        min_hours_between_outbound=settings.min_hours_between_outbound,
    )

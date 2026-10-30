"""Admin API: oversight and intervention.

Auth: X-Admin-Token header. The default token only works in dev mode;
production requires an explicit KARENBOT_ADMIN_TOKEN. Every mutating action
is audited with the admin id.
"""

import uuid
from datetime import UTC, datetime, timedelta
from datetime import date as datetime_date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from karenbot import services
from karenbot.config import get_settings
from karenbot.domain import controls
from karenbot.domain.enums import ExecutionStatus, OutboxStatus
from karenbot.domain.models import (
    AgentAction,
    AuditEvent,
    Case,
    ClaimEvent,
    Communication,
    Company,
    OutboxMessage,
    RecoveryOutcome,
    User,
)
from karenbot.domain.state_machine import InvalidTransition

router = APIRouter()


def require_admin(x_admin_token: str = Header(...)) -> str:
    settings = get_settings()
    expected = settings.admin_token
    if not settings.dev_mode and expected == "dev-admin":
        raise HTTPException(503, "admin token not configured for production")
    if x_admin_token != expected:
        raise HTTPException(403, "invalid admin token")
    return "admin"  # single-admin MVP; real identities arrive with Clerk


def get_db():
    from karenbot.api.main import get_db as _get_db

    yield from _get_db()


class AdminCaseOut(BaseModel):
    id: uuid.UUID
    status: str
    category: str
    company_name: str
    user_email: str
    requested_amount: Decimal | None
    created_at: datetime
    updated_at: datetime


@router.get("/cases", response_model=list[AdminCaseOut])
def list_cases(
    status: str | None = None,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminCaseOut]:
    query = select(Case).order_by(Case.updated_at.desc()).limit(200)
    if status:
        query = query.where(Case.status == status)
    out = []
    for case in db.scalars(query):
        company = db.get(Company, case.company_id)
        user = db.get(User, case.user_id)
        out.append(
            AdminCaseOut(
                id=case.id,
                status=case.status,
                category=case.category,
                company_name=company.name if company else "?",
                user_email=user.email if user else "?",
                requested_amount=case.requested_amount,
                created_at=case.created_at,
                updated_at=case.updated_at,
            )
        )
    return out


@router.post("/cases/{case_id}/pause")
def pause_case(
    case_id: uuid.UUID,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    try:
        services.pause_case(db, case, admin_id=admin, reason="admin pause")
    except InvalidTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": case.status}


@router.post("/cases/{case_id}/resume")
def resume_case(
    case_id: uuid.UUID,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    try:
        services.resume_case(db, case, admin_id=admin)
    except InvalidTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": case.status}


class KillSwitchIn(BaseModel):
    active: bool


@router.post("/kill-switch")
def kill_switch(
    payload: KillSwitchIn,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    controls.set_kill_switch(db, payload.active, admin_id=admin)
    return {"kill_switch_active": payload.active}


@router.get("/kill-switch")
def get_kill_switch(
    admin: str = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    return {"kill_switch_active": controls.kill_switch_active(db)}


class ChannelOut(BaseModel):
    id: uuid.UUID
    company_name: str
    channel: str
    address: str
    purpose: str
    is_escalation: bool
    verified: bool
    verification_source_url: str | None


@router.get("/channels", response_model=list[ChannelOut])
def list_channels(
    verified: bool | None = None,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ChannelOut]:
    from karenbot.domain.models import SupportChannel

    query = select(SupportChannel).where(SupportChannel.active.is_(True))
    if verified is not None:
        query = query.where(SupportChannel.verified.is_(verified))
    out = []
    for ch in db.scalars(query):
        company = db.get(Company, ch.company_id)
        out.append(
            ChannelOut(
                id=ch.id,
                company_name=company.name if company else "?",
                channel=ch.channel,
                address=ch.address,
                purpose=ch.purpose,
                is_escalation=ch.is_escalation,
                verified=ch.verified,
                verification_source_url=ch.verification_source_url,
            )
        )
    out.sort(key=lambda c: (c.verified, c.company_name))
    return out


@router.post("/channels/{channel_id}/verify")
def verify_channel(
    channel_id: uuid.UUID,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Human attestation that the address/URL was checked against its
    source. Only verified channels are ever sendable (policy-enforced)."""
    from karenbot.domain.models import SupportChannel, utcnow

    channel = db.get(SupportChannel, channel_id)
    if channel is None:
        raise HTTPException(404, "channel not found")
    channel.verified = True
    channel.verified_at = utcnow()
    db.add(
        AuditEvent(
            actor_type="admin",
            actor_id=admin,
            event_type="channel.verified",
            event_payload={"channel_id": str(channel_id), "address": channel.address},
        )
    )
    return {"verified": True, "address": channel.address}


@router.post("/channels/{channel_id}/deactivate")
def deactivate_channel(
    channel_id: uuid.UUID,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from karenbot.domain.models import SupportChannel

    channel = db.get(SupportChannel, channel_id)
    if channel is None:
        raise HTTPException(404, "channel not found")
    channel.active = False
    db.add(
        AuditEvent(
            actor_type="admin",
            actor_id=admin,
            event_type="channel.deactivated",
            event_payload={"channel_id": str(channel_id), "address": channel.address},
        )
    )
    return {"active": False}


class InterventionItem(BaseModel):
    kind: str
    case_id: uuid.UUID | None
    detail: str
    timestamp: datetime


@router.get("/intervention-queue", response_model=list[InterventionItem])
def intervention_queue(
    admin: str = Depends(require_admin), db: Session = Depends(get_db)
) -> list[InterventionItem]:
    """Everything that needs a human: unmatched inbound mail, suspected
    injections, denied actions, failed deliveries."""
    items: list[InterventionItem] = []
    week_ago = datetime.now(UTC) - timedelta(days=7)

    flagged = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.event_type.in_(["inbound.unmatched", "security.suspected_injection"]),
            AuditEvent.timestamp >= week_ago,
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(50)
    ).all()
    for event in flagged:
        items.append(
            InterventionItem(
                kind=event.event_type,
                case_id=event.case_id,
                detail=str(event.event_payload)[:300],
                timestamp=event.timestamp,
            )
        )

    denied = db.scalars(
        select(AgentAction)
        .where(
            AgentAction.execution_status == ExecutionStatus.DENIED.value,
            AgentAction.created_at >= week_ago,
        )
        .order_by(AgentAction.created_at.desc())
        .limit(50)
    ).all()
    for action in denied:
        items.append(
            InterventionItem(
                kind="action_denied",
                case_id=action.case_id,
                detail=f"{action.action_type}: {', '.join(action.policy_reasons)}"[:300],
                timestamp=action.created_at,
            )
        )

    failed = db.scalars(
        select(OutboxMessage)
        .where(OutboxMessage.status == OutboxStatus.FAILED.value)
        .order_by(OutboxMessage.updated_at.desc())
        .limit(50)
    ).all()
    for row in failed:
        items.append(
            InterventionItem(
                kind="delivery_failed",
                case_id=row.case_id,
                detail=(row.last_error or "delivery failed")[:300],
                timestamp=row.updated_at,
            )
        )

    items.sort(key=lambda item: item.timestamp, reverse=True)
    return items[:100]


@router.get("/metrics")
def metrics(admin: str = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    by_status = {
        status: count
        for status, count in db.execute(
            select(Case.status, func.count()).group_by(Case.status)
        ).all()
    }
    verified_total = db.scalar(
        select(func.coalesce(func.sum(RecoveryOutcome.amount), 0)).where(
            RecoveryOutcome.verification_status == "verified_received"
        )
    )
    denied_count = db.scalar(
        select(func.count())
        .select_from(AgentAction)
        .where(AgentAction.execution_status == ExecutionStatus.DENIED.value)
    )
    injection_flags = db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.event_type == "security.suspected_injection")
    )
    outbox_counts = {
        status: count
        for status, count in db.execute(
            select(OutboxMessage.status, func.count()).group_by(OutboxMessage.status)
        ).all()
    }
    total_messages = db.scalar(select(func.count()).select_from(Communication))
    return {
        "cases_by_status": by_status,
        "verified_recovered_total": float(verified_total or 0),
        "actions_denied": int(denied_count or 0),
        "injection_flags": int(injection_flags or 0),
        "outbox": outbox_counts,
        "total_communications": int(total_messages or 0),
        "kill_switch_active": controls.kill_switch_active(db),
    }


# ----------------------------------------------------------------------------
# Claimable events: review the research agent's drafts, publish or reject.
# ----------------------------------------------------------------------------


class AdminEventOut(BaseModel):
    id: uuid.UUID
    company_name: str
    title: str
    event_date: datetime_date
    region: str | None
    summary: str
    entitlement: str
    eligibility: str
    how_to_claim: str
    claim_deadline: datetime_date | None
    category: str
    source_urls: list[str]
    status: str
    created_by: str
    research_notes: str | None
    created_at: datetime


def _admin_event_out(event: ClaimEvent) -> AdminEventOut:
    return AdminEventOut(
        id=event.id,
        company_name=event.company_name,
        title=event.title,
        event_date=event.event_date,
        region=event.region,
        summary=event.summary,
        entitlement=event.entitlement,
        eligibility=event.eligibility,
        how_to_claim=event.how_to_claim,
        claim_deadline=event.claim_deadline,
        category=event.category,
        source_urls=event.source_urls or [],
        status=event.status,
        created_by=event.created_by,
        research_notes=event.research_notes,
        created_at=event.created_at,
    )


@router.get("/events", response_model=list[AdminEventOut])
def list_claim_events(
    status: str = "draft",
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminEventOut]:
    query = select(ClaimEvent).order_by(ClaimEvent.event_date.desc())
    if status != "all":
        query = query.where(ClaimEvent.status == status)
    return [_admin_event_out(e) for e in db.scalars(query)]


def _transition_event(
    db: Session, event_id: uuid.UUID, admin: str, new_status: str, event_type: str
) -> AdminEventOut:
    event = db.get(ClaimEvent, event_id)
    if event is None:
        raise HTTPException(404, "event not found")
    if event.status not in ("draft", "published"):
        raise HTTPException(409, f"event is {event.status}")
    event.status = new_status
    db.add(
        AuditEvent(
            actor_type="admin",
            actor_id=admin,
            event_type=event_type,
            event_payload={"event_id": str(event_id), "title": event.title},
        )
    )
    db.flush()
    return _admin_event_out(event)


@router.post("/events/{event_id}/publish", response_model=AdminEventOut)
def publish_claim_event(
    event_id: uuid.UUID,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminEventOut:
    return _transition_event(db, event_id, admin, "published", "claim_event.published")


@router.post("/events/{event_id}/reject", response_model=AdminEventOut)
def reject_claim_event(
    event_id: uuid.UUID,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminEventOut:
    return _transition_event(db, event_id, admin, "rejected", "claim_event.rejected")


@router.post("/events/research")
def research_claim_events_endpoint(
    lookback_days: int = 7,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Run the event-research task now; new findings land as drafts."""
    from karenbot.api.main import _llm
    from karenbot.discovery.event_research import research_claim_events

    counts = research_claim_events(db, _llm(), lookback_days=max(1, min(lookback_days, 31)))
    db.add(
        AuditEvent(
            actor_type="admin",
            actor_id=admin,
            event_type="claim_event.research_run",
            event_payload=counts,
        )
    )
    return counts

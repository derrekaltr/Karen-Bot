"""Customer- and admin-initiated operations (non-LLM side of the product)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.agent.actions import CloseCase, ProposedAction
from karenbot.domain.enums import ActorType, CaseEvent, ExecutionStatus
from karenbot.domain.models import (
    AgentAction,
    AuditEvent,
    Case,
    CaseAuthorization,
    CaseEvidence,
    Company,
    RecoveryOutcome,
    User,
    utcnow,
)
from karenbot.domain.state_machine import transition
from karenbot.policy.context import build_case_context
from karenbot.policy.engine import evaluate
from karenbot.workflows import executor

_action_adapter: TypeAdapter[ProposedAction] = TypeAdapter(ProposedAction)

# Intake consent: granted implicitly when the customer creates a case and
# accepts the product terms. Permits ONLY internal information requests.
INTAKE_ACTIONS = ["request_customer_info"]

# Full negotiation authority, granted explicitly at the authorization step.
# accept_offer remains on the sensitive list and always needs per-use approval.
FULL_ACTIONS = [
    "request_customer_info",
    "send_message",
    "schedule_follow_up",
    "record_offer",
    "accept_offer",
    "recommend_escalation",
    "close_case",
]


def create_case(
    session: Session,
    *,
    user: User,
    company: Company,
    category: str,
    description: str,
    requested_amount: Decimal | None,
    incident_date: datetime | None = None,
) -> Case:
    case = Case(
        user_id=user.id,
        company_id=company.id,
        category=category,
        description=description,
        requested_amount=requested_amount,
        incident_date=incident_date,
    )
    session.add(case)
    session.flush()
    session.add(
        CaseAuthorization(
            case_id=case.id,
            user_id=user.id,
            authorized_actions=INTAKE_ACTIONS,
            authorized_claim_types=[category],
            authorization_version=1,
        )
    )
    session.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            actor_id=str(user.id),
            case_id=case.id,
            event_type="case.created",
            event_payload={"category": category},
        )
    )
    session.flush()
    return case


def add_evidence(
    session: Session, case: Case, *, evidence_type: str, summary: str
) -> CaseEvidence:
    evidence = CaseEvidence(case_id=case.id, evidence_type=evidence_type, summary=summary)
    session.add(evidence)
    session.flush()
    return evidence


def grant_full_authorization(
    session: Session, case: Case, *, max_requested_amount: Decimal | None = None
) -> CaseAuthorization:
    auth = CaseAuthorization(
        case_id=case.id,
        user_id=case.user_id,
        authorized_actions=FULL_ACTIONS,
        authorized_claim_types=[case.category],
        max_requested_amount=max_requested_amount or case.requested_amount,
        authorization_version=2,
    )
    session.add(auth)
    session.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            actor_id=str(case.user_id),
            case_id=case.id,
            event_type="authorization.granted",
            event_payload={"actions": FULL_ACTIONS},
        )
    )
    transition(session, case, CaseEvent.AUTHORIZATION_GRANTED, actor_type=ActorType.CUSTOMER)
    return auth


def revoke_authorization(session: Session, case: Case) -> None:
    """Customer kill switch: revoke all authority and cancel the case."""
    for auth in session.scalars(
        select(CaseAuthorization).where(
            CaseAuthorization.case_id == case.id, CaseAuthorization.revoked_at.is_(None)
        )
    ):
        auth.revoked_at = utcnow()
    session.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            actor_id=str(case.user_id),
            case_id=case.id,
            event_type="authorization.revoked",
        )
    )
    transition(session, case, CaseEvent.CUSTOMER_CANCELED, actor_type=ActorType.CUSTOMER)


def pending_approvals(session: Session, case: Case) -> list[AgentAction]:
    return list(
        session.scalars(
            select(AgentAction).where(
                AgentAction.case_id == case.id,
                AgentAction.execution_status == ExecutionStatus.AWAITING_APPROVAL.value,
            )
        )
    )


def approve_action(session: Session, action_row: AgentAction) -> None:
    action = _action_adapter.validate_python(action_row.proposed_action)
    executor.approve_and_execute(session, action_row, action)


def confirm_recovery_received(session: Session, case: Case) -> None:
    """Customer confirms funds/credit actually arrived; close the case."""
    outcome = session.scalars(
        select(RecoveryOutcome)
        .where(RecoveryOutcome.case_id == case.id)
        .order_by(RecoveryOutcome.created_at.desc())
    ).first()
    if outcome is None:
        raise ValueError("no recovery outcome recorded on case")
    outcome.verification_status = "verified_received"
    outcome.verified_at = utcnow()
    session.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            actor_id=str(case.user_id),
            case_id=case.id,
            event_type="recovery.customer_confirmed",
            event_payload={"outcome_id": str(outcome.id)},
        )
    )
    close = CloseCase(
        case_id=case.id,
        purpose="recovery_verified_by_customer",
        outcome="resolved",
        reason="customer confirmed receipt of recovery",
    )
    row = executor.record_proposal(session, close)
    ctx = build_case_context(session, case)
    executor.apply_decision(session, row, close, evaluate(close, ctx))


def pause_case(session: Session, case: Case, *, admin_id: str, reason: str) -> None:
    transition(
        session,
        case,
        CaseEvent.CASE_BLOCKED,
        actor_type=ActorType.ADMIN,
        actor_id=admin_id,
        payload={"reason": reason},
    )


def resume_case(session: Session, case: Case, *, admin_id: str) -> None:
    transition(session, case, CaseEvent.CASE_RESUMED, actor_type=ActorType.ADMIN, actor_id=admin_id)


def parse_action(row: AgentAction) -> ProposedAction:
    return _action_adapter.validate_python(row.proposed_action)


def get_case(session: Session, case_id: uuid.UUID) -> Case | None:
    return session.get(Case, case_id)

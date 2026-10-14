"""Executor: turns ALLOWed proposals into real system effects.

The executor is the only component that translates a ProposedAction into
side effects (outbox rows, scheduled jobs, state transitions). It trusts the
policy decision it is handed and nothing else; it still resolves recipients
itself from the verified support-channel table, so even an incorrectly
ALLOWed action cannot route to an address of the model's choosing.
"""

from typing import assert_never

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.agent.actions import (
    AcceptOffer,
    CloseCase,
    DraftForCustomer,
    ProposedAction,
    RecommendEscalation,
    RecordOffer,
    RequestCustomerInfo,
    ScheduleFollowUp,
    SendMessage,
)
from karenbot.domain.enums import (
    ActorType,
    CaseEvent,
    CaseStatus,
    Channel,
    Counterparty,
    ExecutionStatus,
    PolicyDecisionType,
)
from karenbot.domain.models import (
    AgentAction,
    AuditEvent,
    Case,
    Communication,
    Conversation,
    RecoveryOutcome,
    ScheduledJob,
    SupportChannel,
    utcnow,
)
from karenbot.domain.state_machine import transition
from karenbot.policy.engine import PolicyDecision
from karenbot.workflows import outbox


class ExecutionRefused(Exception):
    pass


def record_proposal(
    session: Session,
    action: ProposedAction,
    *,
    model_version: str | None = None,
    prompt_version: str | None = None,
) -> AgentAction:
    """Persist a proposal before it is evaluated. Always the first step."""
    row = AgentAction(
        case_id=action.case_id,
        action_type=action.action,
        proposed_action=action.model_dump(mode="json"),
        model_version=model_version,
        prompt_version=prompt_version,
    )
    session.add(row)
    session.flush()
    return row


def apply_decision(
    session: Session, row: AgentAction, action: ProposedAction, decision: PolicyDecision
) -> None:
    """Record the policy verdict and execute if allowed."""
    row.policy_decision = decision.decision.value
    row.policy_reasons = decision.reasons
    session.add(
        AuditEvent(
            actor_type=ActorType.SYSTEM.value,
            case_id=row.case_id,
            event_type=f"policy.{decision.decision.value}",
            event_payload={"agent_action_id": str(row.id), "reasons": decision.reasons},
        )
    )
    if decision.decision == PolicyDecisionType.DENY:
        row.execution_status = ExecutionStatus.DENIED.value
        return
    if decision.decision == PolicyDecisionType.NEEDS_APPROVAL:
        row.execution_status = ExecutionStatus.AWAITING_APPROVAL.value
        return
    _execute(session, row, action)


def approve_and_execute(session: Session, row: AgentAction, action: ProposedAction) -> None:
    """Execute a NEEDS_APPROVAL action after explicit customer approval."""
    if row.execution_status != ExecutionStatus.AWAITING_APPROVAL.value:
        raise ExecutionRefused(f"action is not awaiting approval: {row.execution_status}")
    row.approved_by_user_at = utcnow()
    session.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            case_id=row.case_id,
            event_type="approval.granted",
            event_payload={"agent_action_id": str(row.id)},
        )
    )
    _execute(session, row, action)


def _execute(session: Session, row: AgentAction, action: ProposedAction) -> None:
    case = session.get(Case, row.case_id)
    if case is None:
        raise ExecutionRefused("case not found")

    if isinstance(action, SendMessage):
        channel_row = session.get(SupportChannel, action.support_channel_id)
        if channel_row is None or not channel_row.verified or not channel_row.active:
            raise ExecutionRefused("support channel not verified")  # defense in depth
        conversation = _get_or_create_company_conversation(session, case, channel_row)
        outbox.enqueue(
            session,
            case_id=case.id,
            agent_action_id=row.id,
            conversation_id=conversation.id,
            channel=action.channel.value,
            recipient_address=channel_row.address,
            subject=action.subject,
            body=action.body,
        )
        if case.status == CaseStatus.READY_TO_CONTACT.value:
            transition(session, case, CaseEvent.CONTACT_INITIATED, actor_type=ActorType.AGENT)
        row.execution_status = ExecutionStatus.QUEUED.value

    elif isinstance(action, RequestCustomerInfo):
        if case.status in {CaseStatus.DISCOVERED.value, CaseStatus.ELIGIBILITY_REVIEW.value}:
            transition(
                session,
                case,
                CaseEvent.INFO_REQUESTED,
                actor_type=ActorType.AGENT,
                payload={"questions": action.questions},
            )
        row.execution_status = ExecutionStatus.EXECUTED.value

    elif isinstance(action, ScheduleFollowUp):
        session.add(
            ScheduledJob(
                case_id=case.id,
                job_type="follow_up",
                payload={"note": action.note, "agent_action_id": str(row.id)},
                run_at=action.run_at,
                idempotency_key=f"case:{case.id}:action:{row.id}",
            )
        )
        row.execution_status = ExecutionStatus.EXECUTED.value

    elif isinstance(action, RecordOffer):
        session.add(
            RecoveryOutcome(
                case_id=case.id,
                recovery_type=action.offer_type,
                amount=action.amount,
                currency=action.currency,
                binding=action.binding,
                notes=action.purpose,
            )
        )
        if case.status == CaseStatus.NEGOTIATING.value:
            transition(session, case, CaseEvent.OFFER_MADE, actor_type=ActorType.AGENT)
        row.execution_status = ExecutionStatus.EXECUTED.value

    elif isinstance(action, AcceptOffer):
        outcome = session.get(RecoveryOutcome, action.recovery_outcome_id)
        if outcome is None or outcome.case_id != case.id:
            raise ExecutionRefused("recovery outcome not found on case")
        if case.status == CaseStatus.AWAITING_CUSTOMER_APPROVAL.value:
            transition(session, case, CaseEvent.APPROVAL_GRANTED, actor_type=ActorType.CUSTOMER)
        elif case.status == CaseStatus.OFFER_RECEIVED.value:
            transition(session, case, CaseEvent.OFFER_ACCEPTED, actor_type=ActorType.CUSTOMER)
        row.execution_status = ExecutionStatus.EXECUTED.value

    elif isinstance(action, DraftForCustomer):
        # Respect-the-refusal mode: the draft goes to the CUSTOMER's
        # conversation for them to send personally. Never to the outbox.
        conversation = _get_or_create_customer_conversation(session, case)
        session.add(
            Communication(
                case_id=case.id,
                conversation_id=conversation.id,
                channel=Channel.CHAT.value,
                direction="outbound",
                counterparty=Counterparty.CUSTOMER.value,
                subject=action.subject,
                body=action.body,
                sent_at=utcnow(),
                classification={
                    "draft_for_customer": True,
                    "guidance": action.guidance,
                    "agent_action_id": str(row.id),
                },
            )
        )
        row.execution_status = ExecutionStatus.EXECUTED.value

    elif isinstance(action, RecommendEscalation):
        if case.status == CaseStatus.NEGOTIATING.value:
            transition(
                session,
                case,
                CaseEvent.ESCALATION_STARTED,
                actor_type=ActorType.AGENT,
                payload={"reason": action.reason},
            )
        row.execution_status = ExecutionStatus.EXECUTED.value

    elif isinstance(action, CloseCase):
        if action.outcome == "resolved":
            if case.status == CaseStatus.VERIFYING_RECOVERY.value:
                transition(session, case, CaseEvent.RECOVERY_VERIFIED, actor_type=ActorType.AGENT)
        else:
            transition(
                session, case, CaseEvent.NO_RESPONSE_EXHAUSTED, actor_type=ActorType.AGENT
            )
        row.execution_status = ExecutionStatus.EXECUTED.value

    else:
        assert_never(action)


def _get_or_create_customer_conversation(session: Session, case: Case) -> Conversation:
    conversation = session.scalars(
        select(Conversation).where(
            Conversation.case_id == case.id,
            Conversation.counterparty == Counterparty.CUSTOMER.value,
            Conversation.active.is_(True),
        )
    ).first()
    if conversation is None:
        conversation = Conversation(
            case_id=case.id,
            channel=Channel.CHAT.value,
            counterparty=Counterparty.CUSTOMER.value,
        )
        session.add(conversation)
        session.flush()
    return conversation


def _get_or_create_company_conversation(
    session: Session, case: Case, channel_row: SupportChannel
) -> Conversation:
    conversation = session.scalars(
        select(Conversation).where(
            Conversation.case_id == case.id,
            Conversation.support_channel_id == channel_row.id,
            Conversation.counterparty == Counterparty.COMPANY.value,
            Conversation.active.is_(True),
        )
    ).first()
    if conversation is None:
        conversation = Conversation(
            case_id=case.id,
            channel=channel_row.channel,
            counterparty=Counterparty.COMPANY.value,
            support_channel_id=channel_row.id,
        )
        session.add(conversation)
        session.flush()
    return conversation

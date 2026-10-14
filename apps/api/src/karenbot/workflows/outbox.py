"""Transactional outbox: exactly-once outbound delivery.

Lifecycle: pending -> sending -> sent (or failed). Claims are atomic
compare-and-set UPDATEs, portable across Postgres and SQLite. If a worker
dies between provider send and the sent-mark, recovery asks the provider
whether the idempotency key already went out before retrying.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from karenbot.channels.base import ChannelAdapter, OutboundMessage
from karenbot.channels.base import SendReceipt as _SendReceipt
from karenbot.domain.enums import (
    ActorType,
    CaseEvent,
    CaseStatus,
    Direction,
    ExecutionStatus,
    OutboxStatus,
)
from karenbot.domain.models import (
    AgentAction,
    AuditEvent,
    Case,
    Communication,
    Conversation,
    OutboxMessage,
    utcnow,
)
from karenbot.domain.state_machine import transition

MAX_ATTEMPTS = 5


def claim_next(session: Session, worker_id: str, lease_seconds: int = 300) -> OutboxMessage | None:
    """Atomically claim the oldest pending outbox row, or None."""
    row_id = session.scalars(
        select(OutboxMessage.id)
        .where(OutboxMessage.status == OutboxStatus.PENDING.value)
        .order_by(OutboxMessage.created_at)
        .limit(1)
    ).first()
    if row_id is None:
        return None
    claimed: CursorResult[Any] = session.execute(  # type: ignore[assignment]
        update(OutboxMessage)
        .where(OutboxMessage.id == row_id, OutboxMessage.status == OutboxStatus.PENDING.value)
        .values(
            status=OutboxStatus.SENDING.value,
            locked_by=worker_id,
            locked_until=datetime.now(UTC) + timedelta(seconds=lease_seconds),
            attempts=OutboxMessage.attempts + 1,
        )
    )
    session.commit()
    if claimed.rowcount != 1:
        return None  # another worker won the race
    return session.get(OutboxMessage, row_id)


def deliver(session: Session, row: OutboxMessage, adapter: ChannelAdapter) -> None:
    """Send a claimed row and finalize it. Caller handles exceptions."""
    thread_id = session.scalar(
        select(Conversation.provider_thread_id).where(Conversation.id == row.conversation_id)
    )
    # RFC-2822 threading for providers without native threads: reply to the
    # most recent inbound message in this conversation.
    last_inbound = session.scalars(
        select(Communication)
        .where(
            Communication.conversation_id == row.conversation_id,
            Communication.direction == Direction.INBOUND.value,
        )
        .order_by(Communication.created_at.desc())
    ).first()
    metadata: dict = {}
    if last_inbound is not None and last_inbound.provider_message_id:
        metadata["in_reply_to"] = last_inbound.provider_message_id
        metadata["references"] = [last_inbound.provider_message_id]
    try:
        receipt = adapter.send(
            OutboundMessage(
                idempotency_key=row.idempotency_key,
                recipient_address=row.recipient_address,
                subject=row.subject,
                body=row.body,
                thread_provider_id=thread_id,
                metadata=metadata,
            )
        )
    except Exception as exc:
        _record_failure(session, row, exc)
        raise
    _finalize_sent(session, row, receipt)
    session.commit()


def _record_failure(session: Session, row: OutboxMessage, exc: Exception) -> None:
    row.last_error = repr(exc)
    if row.attempts >= MAX_ATTEMPTS:
        row.status = OutboxStatus.FAILED.value
    else:
        row.status = OutboxStatus.PENDING.value
        row.locked_by = None
        row.locked_until = None
    session.commit()


def _finalize_sent(session: Session, row: OutboxMessage, receipt: _SendReceipt) -> None:
    row.status = OutboxStatus.SENT.value
    row.provider_message_id = receipt.provider_message_id
    row.provider_thread_id = receipt.provider_thread_id
    row.sent_at = utcnow()

    conversation = session.get(Conversation, row.conversation_id)
    assert conversation is not None
    if conversation.provider_thread_id is None:
        conversation.provider_thread_id = receipt.provider_thread_id

    # Idempotent communication record (unique on channel + provider_message_id).
    existing = session.scalars(
        select(Communication).where(
            Communication.channel == row.channel,
            Communication.provider_message_id == receipt.provider_message_id,
        )
    ).first()
    action = session.get(AgentAction, row.agent_action_id)
    if existing is None:
        session.add(
            Communication(
                case_id=row.case_id,
                conversation_id=row.conversation_id,
                channel=row.channel,
                direction=Direction.OUTBOUND.value,
                counterparty=conversation.counterparty,
                provider_message_id=receipt.provider_message_id,
                subject=row.subject,
                body=row.body,
                sent_at=row.sent_at,
                delivery_status="sent",
                classification={
                    "is_follow_up": bool(
                        action and action.proposed_action.get("is_follow_up", False)
                    ),
                    "agent_action_id": str(row.agent_action_id),
                },
            )
        )
    if action is not None:
        action.execution_status = ExecutionStatus.EXECUTED.value

    case = session.get(Case, row.case_id)
    assert case is not None
    if case.status in {
        CaseStatus.CONTACTING_COMPANY.value,
        CaseStatus.NEGOTIATING.value,
        CaseStatus.ESCALATED.value,
    }:
        transition(session, case, CaseEvent.MESSAGE_SENT, actor_type=ActorType.SYSTEM)

    session.add(
        AuditEvent(
            actor_type=ActorType.SYSTEM.value,
            case_id=row.case_id,
            event_type="outbox.sent",
            event_payload={
                "outbox_id": str(row.id),
                "idempotency_key": row.idempotency_key,
                "provider_message_id": receipt.provider_message_id,
            },
        )
    )


def stuck_rows(session: Session) -> list[OutboxMessage]:
    now = datetime.now(UTC)
    return list(
        session.scalars(
            select(OutboxMessage).where(
                OutboxMessage.status == OutboxStatus.SENDING.value,
                OutboxMessage.locked_until < now,
            )
        )
    )


def recover_row(session: Session, row: OutboxMessage, adapter: ChannelAdapter) -> None:
    """Resolve one row stuck in 'sending' past its lease. If the provider
    confirms the idempotency key went out, finalize as sent; otherwise
    requeue. Never blind-resend. Caller commits."""
    receipt = adapter.find_by_idempotency_key(row.idempotency_key)
    if receipt is not None:
        _finalize_sent(session, row, receipt)
    else:
        row.status = OutboxStatus.PENDING.value
        row.locked_by = None
        row.locked_until = None


def recover_stuck(session: Session, adapter: ChannelAdapter) -> int:
    rows = stuck_rows(session)
    for row in rows:
        recover_row(session, row, adapter)
    session.commit()
    return len(rows)


def enqueue(
    session: Session,
    *,
    case_id: uuid.UUID,
    agent_action_id: uuid.UUID,
    conversation_id: uuid.UUID,
    channel: str,
    recipient_address: str,
    subject: str | None,
    body: str,
) -> OutboxMessage:
    row = OutboxMessage(
        case_id=case_id,
        agent_action_id=agent_action_id,
        conversation_id=conversation_id,
        channel=channel,
        recipient_address=recipient_address,
        subject=subject,
        body=body,
        idempotency_key=f"case:{case_id}:action:{agent_action_id}",
    )
    session.add(row)
    session.flush()
    return row

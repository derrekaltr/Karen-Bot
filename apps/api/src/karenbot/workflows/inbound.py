"""Inbound message processing: thread matching and ingestion.

Hard rule: an inbound message that cannot be confidently matched to a
conversation is NEVER auto-attached to a case. It is recorded for human
review instead.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.channels.base import ChannelAdapter, InboundMessage
from karenbot.domain.enums import ActorType, CaseEvent, CaseStatus, Counterparty, Direction
from karenbot.domain.models import AuditEvent, Case, Communication, Conversation
from karenbot.domain.state_machine import transition


def poll_inbound(session: Session, adapter: ChannelAdapter) -> list[Communication]:
    """Fetch and ingest new inbound messages. Returns newly created rows."""
    created: list[Communication] = []
    for message in adapter.fetch_inbound():
        comm = ingest_inbound(session, adapter.channel.value, message)
        if comm is not None:
            created.append(comm)
    return created


def ingest_inbound(
    session: Session, channel: str, message: InboundMessage
) -> Communication | None:
    # Dedupe on provider message id.
    existing = session.scalars(
        select(Communication).where(
            Communication.channel == channel,
            Communication.provider_message_id == message.provider_message_id,
        )
    ).first()
    if existing is not None:
        return None

    conversation = None
    if message.provider_thread_id:
        conversation = session.scalars(
            select(Conversation).where(
                Conversation.channel == channel,
                Conversation.provider_thread_id == message.provider_thread_id,
            )
        ).first()

    if conversation is None:
        # Unmatched: route to human review, never guess.
        session.add(
            AuditEvent(
                actor_type=ActorType.SYSTEM.value,
                event_type="inbound.unmatched",
                event_payload={
                    "channel": channel,
                    "provider_message_id": message.provider_message_id,
                    "provider_thread_id": message.provider_thread_id,
                    "from_address": message.from_address,
                    "subject": message.subject,
                },
            )
        )
        session.flush()
        return None

    comm = Communication(
        case_id=conversation.case_id,
        conversation_id=conversation.id,
        channel=channel,
        direction=Direction.INBOUND.value,
        counterparty=conversation.counterparty,
        provider_message_id=message.provider_message_id,
        subject=message.subject,
        body=message.body,
        received_at=message.received_at,
    )
    session.add(comm)

    case = session.get(Case, conversation.case_id)
    if (
        case is not None
        and conversation.counterparty == Counterparty.COMPANY.value
        and case.status == CaseStatus.AWAITING_RESPONSE.value
    ):
        transition(session, case, CaseEvent.REPLY_RECEIVED, actor_type=ActorType.SYSTEM)
    session.flush()
    return comm

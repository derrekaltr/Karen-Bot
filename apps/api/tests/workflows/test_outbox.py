"""Exactly-once delivery: crash, restart, and retry behavior."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from karenbot.channels.mock_email import MockEmailAdapter
from karenbot.domain.enums import OutboxStatus
from karenbot.domain.models import AgentAction, Communication, Conversation, OutboxMessage
from karenbot.workflows import outbox


def _setup_outbox_row(session, ids):
    action = AgentAction(
        case_id=ids["case_id"], action_type="send_message", proposed_action={"is_follow_up": False}
    )
    conversation = Conversation(
        case_id=ids["case_id"],
        channel="email",
        counterparty="company",
        support_channel_id=ids["channel_id"],
    )
    session.add_all([action, conversation])
    session.flush()
    row = outbox.enqueue(
        session,
        case_id=ids["case_id"],
        agent_action_id=action.id,
        conversation_id=conversation.id,
        channel="email",
        recipient_address="refunds@acme.example",
        subject="Request",
        body="Please reimburse $350.",
    )
    session.commit()
    return row.id


def test_claim_and_deliver_sends_exactly_once(seeded):
    db, ids = seeded
    adapter = MockEmailAdapter()
    with db() as session:
        row_id = _setup_outbox_row(session, ids)
    with db() as session:
        row = outbox.claim_next(session, "w1")
        assert row is not None and row.id == row_id
        outbox.deliver(session, row, adapter)
    assert len(adapter.sent) == 1
    with db() as session:
        row = session.get(OutboxMessage, row_id)
        assert row.status == OutboxStatus.SENT.value
        assert row.provider_message_id
        comm = session.scalars(
            select(Communication).where(Communication.case_id == ids["case_id"])
        ).all()
        assert len(comm) == 1
        # Nothing left to claim.
        assert outbox.claim_next(session, "w1") is None


def test_crash_after_send_recovers_without_duplicate(seeded):
    """Worker dies between provider send and the sent-mark."""
    db, ids = seeded
    adapter = MockEmailAdapter()
    with db() as session:
        row_id = _setup_outbox_row(session, ids)
    with db() as session:
        row = outbox.claim_next(session, "w1")
        # Simulate: provider send succeeded...
        from karenbot.channels.base import OutboundMessage

        adapter.send(
            OutboundMessage(
                idempotency_key=row.idempotency_key,
                recipient_address=row.recipient_address,
                subject=row.subject,
                body=row.body,
            )
        )
        # ...then the worker crashed before finalizing. Expire the lease.
        row.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    # A fresh worker recovers: finds the provider-side receipt, finalizes,
    # and does NOT resend.
    with db() as session:
        outbox.recover_stuck(session, adapter)
        row = session.get(OutboxMessage, row_id)
        assert row.status == OutboxStatus.SENT.value
    assert len(adapter.sent) == 1


def test_crash_before_send_requeues_and_sends_once(seeded):
    db, ids = seeded
    adapter = MockEmailAdapter()
    with db() as session:
        row_id = _setup_outbox_row(session, ids)
    with db() as session:
        row = outbox.claim_next(session, "w1")
        # Crash before any provider call: lease expires with nothing sent.
        row.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    with db() as session:
        outbox.recover_stuck(session, adapter)
        row = session.get(OutboxMessage, row_id)
        assert row.status == OutboxStatus.PENDING.value
    with db() as session:
        row = outbox.claim_next(session, "w2")
        outbox.deliver(session, row, adapter)
    assert len(adapter.sent) == 1


def test_provider_failure_requeues_then_succeeds(seeded):
    db, ids = seeded
    adapter = MockEmailAdapter()
    adapter.fail_next_send = True
    with db() as session:
        row_id = _setup_outbox_row(session, ids)
    with db() as session:
        row = outbox.claim_next(session, "w1")
        try:
            outbox.deliver(session, row, adapter)
        except ConnectionError:
            pass
    with db() as session:
        row = session.get(OutboxMessage, row_id)
        assert row.status == OutboxStatus.PENDING.value
        assert "ConnectionError" in row.last_error
    with db() as session:
        row = outbox.claim_next(session, "w1")
        outbox.deliver(session, row, adapter)
    assert len(adapter.sent) == 1


def test_provider_idempotency_dedupes_same_key(seeded):
    """Even if the same key is sent twice, the provider-side guard holds."""
    from karenbot.channels.base import OutboundMessage

    adapter = MockEmailAdapter()
    msg = OutboundMessage(
        idempotency_key="case:x:action:y",
        recipient_address="a@b.c",
        subject="s",
        body="b",
    )
    r1 = adapter.send(msg)
    r2 = adapter.send(msg)
    assert r1 == r2
    assert len(adapter.sent) == 1

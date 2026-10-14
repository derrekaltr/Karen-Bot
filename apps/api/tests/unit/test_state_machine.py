from decimal import Decimal

import pytest
from sqlalchemy import select

from karenbot.domain.enums import ActorType, CaseEvent, CaseStatus
from karenbot.domain.models import AuditEvent, Case, Company, User
from karenbot.domain.state_machine import InvalidTransition, transition


@pytest.fixture
def case_session(db):
    with db() as session:
        user = User(email="t@example.com")
        company = Company(name="TestCo", industry="airline")
        session.add_all([user, company])
        session.flush()
        case = Case(
            user_id=user.id,
            company_id=company.id,
            category="refund",
            description="x",
            requested_amount=Decimal("100"),
        )
        session.add(case)
        session.flush()
        yield session, case


HAPPY_PATH = [
    (CaseEvent.INFO_REQUESTED, CaseStatus.AWAITING_INFORMATION),
    (CaseEvent.INFO_RECEIVED, CaseStatus.ELIGIBILITY_REVIEW),
    (CaseEvent.ELIGIBILITY_CONFIRMED, CaseStatus.AWAITING_AUTHORIZATION),
    (CaseEvent.AUTHORIZATION_GRANTED, CaseStatus.READY_TO_CONTACT),
    (CaseEvent.CONTACT_INITIATED, CaseStatus.CONTACTING_COMPANY),
    (CaseEvent.MESSAGE_SENT, CaseStatus.AWAITING_RESPONSE),
    (CaseEvent.REPLY_RECEIVED, CaseStatus.NEGOTIATING),
    (CaseEvent.OFFER_MADE, CaseStatus.OFFER_RECEIVED),
    (CaseEvent.APPROVAL_REQUESTED, CaseStatus.AWAITING_CUSTOMER_APPROVAL),
    (CaseEvent.APPROVAL_GRANTED, CaseStatus.VERIFYING_RECOVERY),
    (CaseEvent.RECOVERY_VERIFIED, CaseStatus.RESOLVED),
]


def test_happy_path_walks_every_transition(case_session):
    session, case = case_session
    for event, expected in HAPPY_PATH:
        new = transition(session, case, event, actor_type=ActorType.SYSTEM)
        assert new == expected
        assert case.status == expected.value


def test_illegal_transitions_rejected(case_session):
    session, case = case_session
    with pytest.raises(InvalidTransition):
        transition(session, case, CaseEvent.MESSAGE_SENT, actor_type=ActorType.AGENT)
    with pytest.raises(InvalidTransition):
        transition(session, case, CaseEvent.OFFER_ACCEPTED, actor_type=ActorType.AGENT)
    assert case.status == CaseStatus.DISCOVERED.value  # unchanged


def test_terminal_states_are_terminal(case_session):
    session, case = case_session
    transition(session, case, CaseEvent.CUSTOMER_CANCELED, actor_type=ActorType.CUSTOMER)
    for event in CaseEvent:
        with pytest.raises(InvalidTransition):
            transition(session, case, event, actor_type=ActorType.SYSTEM)


def test_block_and_resume_restores_previous_state(case_session):
    session, case = case_session
    transition(session, case, CaseEvent.INFO_REQUESTED, actor_type=ActorType.AGENT)
    transition(session, case, CaseEvent.CASE_BLOCKED, actor_type=ActorType.ADMIN)
    assert case.status == CaseStatus.BLOCKED.value
    assert case.previous_status == CaseStatus.AWAITING_INFORMATION.value
    transition(session, case, CaseEvent.CASE_RESUMED, actor_type=ActorType.ADMIN)
    assert case.status == CaseStatus.AWAITING_INFORMATION.value
    assert case.previous_status is None


def test_every_transition_writes_an_audit_event(case_session):
    session, case = case_session
    transition(session, case, CaseEvent.INTAKE_COMPLETE, actor_type=ActorType.AGENT)
    transition(session, case, CaseEvent.ELIGIBILITY_CONFIRMED, actor_type=ActorType.AGENT)
    events = session.scalars(select(AuditEvent).where(AuditEvent.case_id == case.id)).all()
    types = [e.event_type for e in events]
    assert "case.intake_complete" in types
    assert "case.eligibility_confirmed" in types
    payload = events[-1].event_payload
    assert payload["from_status"] == "ELIGIBILITY_REVIEW"
    assert payload["to_status"] == "AWAITING_AUTHORIZATION"

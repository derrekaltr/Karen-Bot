"""The single legal-transition function for case state.

Every case status change in the system MUST go through `transition()`, which
validates the move against an explicit transition table and writes an audit
event in the same database transaction. Out-of-band mutation of
`Case.status` is a bug.
"""

from typing import Any

from sqlalchemy.orm import Session

from karenbot.domain.enums import ACTIVE_STATES, ActorType, CaseEvent, CaseStatus
from karenbot.domain.models import AuditEvent, Case


class InvalidTransition(Exception):
    def __init__(self, status: str, event: CaseEvent):
        super().__init__(f"Event {event} is not legal from status {status}")
        self.status = status
        self.event = event


# (current status, event) -> next status.
TRANSITION_TABLE: dict[tuple[CaseStatus, CaseEvent], CaseStatus] = {
    # Intake
    (CaseStatus.DISCOVERED, CaseEvent.INFO_REQUESTED): CaseStatus.AWAITING_INFORMATION,
    (CaseStatus.DISCOVERED, CaseEvent.INTAKE_COMPLETE): CaseStatus.ELIGIBILITY_REVIEW,
    (CaseStatus.AWAITING_INFORMATION, CaseEvent.INFO_RECEIVED): CaseStatus.ELIGIBILITY_REVIEW,
    (CaseStatus.ELIGIBILITY_REVIEW, CaseEvent.INFO_REQUESTED): CaseStatus.AWAITING_INFORMATION,
    # Eligibility and authorization
    (CaseStatus.ELIGIBILITY_REVIEW, CaseEvent.ELIGIBILITY_CONFIRMED): CaseStatus.AWAITING_AUTHORIZATION,
    (CaseStatus.ELIGIBILITY_REVIEW, CaseEvent.ELIGIBILITY_REJECTED): CaseStatus.CLOSED_UNSUCCESSFUL,
    (CaseStatus.AWAITING_AUTHORIZATION, CaseEvent.AUTHORIZATION_GRANTED): CaseStatus.READY_TO_CONTACT,
    # Contact loop
    (CaseStatus.READY_TO_CONTACT, CaseEvent.CONTACT_INITIATED): CaseStatus.CONTACTING_COMPANY,
    (CaseStatus.CONTACTING_COMPANY, CaseEvent.MESSAGE_SENT): CaseStatus.AWAITING_RESPONSE,
    (CaseStatus.AWAITING_RESPONSE, CaseEvent.REPLY_RECEIVED): CaseStatus.NEGOTIATING,
    (CaseStatus.NEGOTIATING, CaseEvent.MESSAGE_SENT): CaseStatus.AWAITING_RESPONSE,
    (CaseStatus.AWAITING_RESPONSE, CaseEvent.NO_RESPONSE_EXHAUSTED): CaseStatus.ESCALATED,
    # Escalation
    (CaseStatus.NEGOTIATING, CaseEvent.ESCALATION_STARTED): CaseStatus.ESCALATED,
    (CaseStatus.ESCALATED, CaseEvent.MESSAGE_SENT): CaseStatus.AWAITING_RESPONSE,
    (CaseStatus.ESCALATED, CaseEvent.ESCALATION_REPLY): CaseStatus.NEGOTIATING,
    (CaseStatus.ESCALATED, CaseEvent.NO_RESPONSE_EXHAUSTED): CaseStatus.CLOSED_UNSUCCESSFUL,
    # Offers
    (CaseStatus.NEGOTIATING, CaseEvent.OFFER_MADE): CaseStatus.OFFER_RECEIVED,
    (CaseStatus.OFFER_RECEIVED, CaseEvent.OFFER_DECLINED): CaseStatus.NEGOTIATING,
    (CaseStatus.OFFER_RECEIVED, CaseEvent.OFFER_ACCEPTED): CaseStatus.VERIFYING_RECOVERY,
    (CaseStatus.OFFER_RECEIVED, CaseEvent.APPROVAL_REQUESTED): CaseStatus.AWAITING_CUSTOMER_APPROVAL,
    (CaseStatus.NEGOTIATING, CaseEvent.APPROVAL_REQUESTED): CaseStatus.AWAITING_CUSTOMER_APPROVAL,
    (CaseStatus.AWAITING_CUSTOMER_APPROVAL, CaseEvent.APPROVAL_GRANTED): CaseStatus.VERIFYING_RECOVERY,
    (CaseStatus.AWAITING_CUSTOMER_APPROVAL, CaseEvent.APPROVAL_DENIED): CaseStatus.NEGOTIATING,
    # Verification
    (CaseStatus.VERIFYING_RECOVERY, CaseEvent.RECOVERY_VERIFIED): CaseStatus.RESOLVED,
    (CaseStatus.VERIFYING_RECOVERY, CaseEvent.RECOVERY_NOT_VERIFIED): CaseStatus.NEGOTIATING,
    # Dead ends
    (CaseStatus.NEGOTIATING, CaseEvent.NO_RESPONSE_EXHAUSTED): CaseStatus.CLOSED_UNSUCCESSFUL,
}


def transition(
    session: Session,
    case: Case,
    event: CaseEvent,
    *,
    actor_type: ActorType,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> CaseStatus:
    """Apply `event` to `case`, or raise InvalidTransition.

    Writes the status change and an audit event; the caller owns the
    transaction (commit/rollback), so the change and its audit record are
    atomic.
    """
    current = CaseStatus(case.status)

    if event == CaseEvent.CUSTOMER_CANCELED:
        if current not in ACTIVE_STATES:
            raise InvalidTransition(case.status, event)
        new_status = CaseStatus.CANCELED
    elif event == CaseEvent.CASE_BLOCKED:
        if current not in ACTIVE_STATES:
            raise InvalidTransition(case.status, event)
        case.previous_status = current.value
        new_status = CaseStatus.BLOCKED
    elif event == CaseEvent.CASE_RESUMED:
        if current != CaseStatus.BLOCKED or not case.previous_status:
            raise InvalidTransition(case.status, event)
        new_status = CaseStatus(case.previous_status)
        case.previous_status = None
    else:
        try:
            new_status = TRANSITION_TABLE[(current, event)]
        except KeyError:
            raise InvalidTransition(case.status, event) from None

    case.status = new_status.value
    session.add(
        AuditEvent(
            actor_type=actor_type.value,
            actor_id=actor_id,
            case_id=case.id,
            event_type=f"case.{event.value.lower()}",
            event_payload={
                "from_status": current.value,
                "to_status": new_status.value,
                **(payload or {}),
            },
        )
    )
    session.flush()
    return new_status

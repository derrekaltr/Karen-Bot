from enum import StrEnum


class CaseStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    AWAITING_INFORMATION = "AWAITING_INFORMATION"
    ELIGIBILITY_REVIEW = "ELIGIBILITY_REVIEW"
    AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
    READY_TO_CONTACT = "READY_TO_CONTACT"
    CONTACTING_COMPANY = "CONTACTING_COMPANY"
    AWAITING_RESPONSE = "AWAITING_RESPONSE"
    NEGOTIATING = "NEGOTIATING"
    ESCALATED = "ESCALATED"
    AWAITING_CUSTOMER_APPROVAL = "AWAITING_CUSTOMER_APPROVAL"
    OFFER_RECEIVED = "OFFER_RECEIVED"
    VERIFYING_RECOVERY = "VERIFYING_RECOVERY"
    RESOLVED = "RESOLVED"
    CLOSED_UNSUCCESSFUL = "CLOSED_UNSUCCESSFUL"
    CANCELED = "CANCELED"
    BLOCKED = "BLOCKED"


# States in which the agent may still act. Terminal states are everything else.
ACTIVE_STATES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.DISCOVERED,
        CaseStatus.AWAITING_INFORMATION,
        CaseStatus.ELIGIBILITY_REVIEW,
        CaseStatus.AWAITING_AUTHORIZATION,
        CaseStatus.READY_TO_CONTACT,
        CaseStatus.CONTACTING_COMPANY,
        CaseStatus.AWAITING_RESPONSE,
        CaseStatus.NEGOTIATING,
        CaseStatus.ESCALATED,
        CaseStatus.AWAITING_CUSTOMER_APPROVAL,
        CaseStatus.OFFER_RECEIVED,
        CaseStatus.VERIFYING_RECOVERY,
    }
)

# States from which outbound company contact is permitted at all.
CONTACTABLE_STATES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.READY_TO_CONTACT,
        CaseStatus.CONTACTING_COMPANY,
        CaseStatus.AWAITING_RESPONSE,
        CaseStatus.NEGOTIATING,
        CaseStatus.ESCALATED,
        CaseStatus.OFFER_RECEIVED,
        # Correspondence continues during verification: acceptance
        # confirmations, "where is the payment" nudges.
        CaseStatus.VERIFYING_RECOVERY,
    }
)


class CaseEvent(StrEnum):
    INFO_REQUESTED = "INFO_REQUESTED"
    INFO_RECEIVED = "INFO_RECEIVED"
    INTAKE_COMPLETE = "INTAKE_COMPLETE"
    ELIGIBILITY_CONFIRMED = "ELIGIBILITY_CONFIRMED"
    ELIGIBILITY_REJECTED = "ELIGIBILITY_REJECTED"
    AUTHORIZATION_GRANTED = "AUTHORIZATION_GRANTED"
    CONTACT_INITIATED = "CONTACT_INITIATED"
    MESSAGE_SENT = "MESSAGE_SENT"
    REPLY_RECEIVED = "REPLY_RECEIVED"
    OFFER_MADE = "OFFER_MADE"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    OFFER_DECLINED = "OFFER_DECLINED"
    ESCALATION_STARTED = "ESCALATION_STARTED"
    ESCALATION_REPLY = "ESCALATION_REPLY"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    RECOVERY_NOT_VERIFIED = "RECOVERY_NOT_VERIFIED"
    NO_RESPONSE_EXHAUSTED = "NO_RESPONSE_EXHAUSTED"
    CUSTOMER_CANCELED = "CUSTOMER_CANCELED"
    CASE_BLOCKED = "CASE_BLOCKED"
    CASE_RESUMED = "CASE_RESUMED"


class CompanySizeClass(StrEnum):
    """Targeting classification — KarenBot's moral code.

    KarenBot pursues large enterprises (national chains, airlines, card
    networks, platforms), never mom-and-pop businesses. Companies are
    UNCLASSIFIED until a human classifies them, and unclassified companies
    are NOT targetable: the safe default is to leave a business alone.
    """

    ENTERPRISE = "enterprise"  # Delta, Uber, Amex, McDonald's, Chipotle, ...
    MID_MARKET = "mid_market"  # regional chains; targetable only if enabled
    SMALL_BUSINESS = "small_business"  # mom-and-pop: never targetable
    UNCLASSIFIED = "unclassified"  # not yet reviewed: never targetable


class Channel(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    VOICE = "voice"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Counterparty(StrEnum):
    COMPANY = "company"
    CUSTOMER = "customer"


class PolicyDecisionType(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"


class ExecutionStatus(StrEnum):
    PROPOSED = "proposed"
    AWAITING_APPROVAL = "awaiting_approval"
    DENIED = "denied"
    QUEUED = "queued"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELED = "canceled"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    CUSTOMER_CONFIRMED = "customer_confirmed"
    DOCUMENTED = "documented"
    COMPANY_CONFIRMED = "company_confirmed"
    VERIFIED_RECEIVED = "verified_received"


class ActorType(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"
    ADMIN = "admin"

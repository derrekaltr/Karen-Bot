"""KarenBot relational schema.

Design rules:
- UUID primary keys everywhere; timestamps are timezone-aware UTC.
- Enum columns are stored as plain strings (portable across Postgres and the
  SQLite test database); Python-side typing uses StrEnum values.
- Secrets and raw content bodies larger than a row should live in object
  storage; columns named *_reference hold storage pointers, not plaintext.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from karenbot.db.base import Base
from karenbot.domain.enums import (
    CaseStatus,
    ExecutionStatus,
    JobStatus,
    OutboxStatus,
    VerificationStatus,
)

JSONVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    clerk_user_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    account_status: Mapped[str] = mapped_column(String(40), default="active")

    cases: Mapped[list["Case"]] = relationship(back_populates="user")


class ConnectedAccount(TimestampMixin, Base):
    __tablename__ = "connected_accounts"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(40))  # "gmail", later "outlook"
    provider_account_id: Mapped[str] = mapped_column(String(320))
    encrypted_token_reference: Mapped[str | None] = mapped_column(Text)
    granted_scopes: Mapped[list[str]] = mapped_column(JSONVariant, default=list)
    status: Mapped[str] = mapped_column(String(40), default="active")
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "provider", "provider_account_id"),)


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), unique=True)
    industry: Mapped[str] = mapped_column(String(80))  # "airline", "hotel", "ecommerce"
    website: Mapped[str | None] = mapped_column(String(500))
    supported_status: Mapped[str] = mapped_column(String(40), default="supported")
    # Moral code: only large companies are fair game (see CompanySizeClass).
    # Defaults to unclassified, which is NOT targetable until a human review
    # sets it. Mom-and-pop businesses are never targeted.
    size_class: Mapped[str] = mapped_column(String(40), default="unclassified")
    # Respect-the-refusal: set when the company states it only deals with
    # customers directly. Agent-sent outreach stops; KarenBot switches to
    # drafting messages the customer sends personally. Never evaded.
    refuses_third_party: Mapped[bool] = mapped_column(default=False)
    # Generosity intelligence (docs/research/company-generosity.md):
    # {goodwill_low, goodwill_high (USD-equivalent), goodwill_unit,
    #  best_channel, notes, evidence}. INTERNAL TARGETING ONLY — never
    # asserted to companies in negotiation.
    intel: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)

    support_channels: Mapped[list["SupportChannel"]] = relationship(back_populates="company")
    policies: Mapped[list["CompanyPolicy"]] = relationship(back_populates="company")


class SupportChannel(TimestampMixin, Base):
    """A verified, permitted contact route for a company.

    The agent may only ever reference these by id; it never supplies raw
    addresses. Verification provenance is mandatory.
    """

    __tablename__ = "support_channels"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    channel: Mapped[str] = mapped_column(String(20))  # Channel enum value
    address: Mapped[str] = mapped_column(String(500))  # email addr / chat URL / phone number
    purpose: Mapped[str] = mapped_column(String(200))  # e.g. "refunds", "baggage claims"
    is_escalation: Mapped[bool] = mapped_column(default=False)
    verified: Mapped[bool] = mapped_column(default=False)
    verification_source_url: Mapped[str | None] = mapped_column(String(1000))
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(default=True)

    company: Mapped[Company] = relationship(back_populates="support_channels")


class CompanyPolicy(TimestampMixin, Base):
    __tablename__ = "company_policies"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    policy_type: Mapped[str] = mapped_column(String(80))  # e.g. "baggage_reimbursement"
    jurisdiction: Mapped[str] = mapped_column(String(40), default="US")
    source_url: Mapped[str | None] = mapped_column(String(1000))
    effective_date: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    content: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    # Deterministic eligibility rules for this policy, evaluated by
    # karenbot.agent.eligibility — the LLM never decides entitlement.
    eligibility_rules: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)

    company: Mapped[Company] = relationship(back_populates="policies")


class Case(TimestampMixin, Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    category: Mapped[str] = mapped_column(String(80))  # claim type, e.g. "baggage_delay_expenses"
    description: Mapped[str] = mapped_column(Text)
    incident_date: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    requested_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(40), default=CaseStatus.DISCOVERED.value)
    # Set when status == BLOCKED so CASE_RESUMED can restore the prior state.
    previous_status: Mapped[str | None] = mapped_column(String(40))
    # "agent": KarenBot contacts the company itself (targetable companies).
    # "assist": KarenBot only drafts messages the customer sends personally
    # (non-enterprise merchants, respect-the-refusal, moral-code cases).
    contact_mode: Mapped[str] = mapped_column(String(20), default="agent")
    # Structured facts extracted at intake (flight numbers, order ids, ...).
    facts: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    eligibility_basis: Mapped[str | None] = mapped_column(String(40))  # "entitlement" | "goodwill"

    user: Mapped[User] = relationship(back_populates="cases")
    company: Mapped[Company] = relationship()
    authorizations: Mapped[list["CaseAuthorization"]] = relationship(back_populates="case")
    evidence: Mapped[list["CaseEvidence"]] = relationship(back_populates="case")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="case")

    __table_args__ = (Index("ix_cases_user_status", "user_id", "status"),)


class CaseAuthorization(TimestampMixin, Base):
    """Documented, case-specific grant of authority from the customer."""

    __tablename__ = "case_authorizations"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    authorized_actions: Mapped[list[str]] = mapped_column(JSONVariant, default=list)
    prohibited_actions: Mapped[list[str]] = mapped_column(JSONVariant, default=list)
    authorized_claim_types: Mapped[list[str]] = mapped_column(JSONVariant, default=list)
    max_requested_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2))
    authorization_version: Mapped[int] = mapped_column(default=1)
    consent_timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # Letter of Authorization: the signed text granting agency, plus
    # signature provenance. This is the defense file for any
    # "who authorized you?" challenge — see docs/legal-risk.md.
    loa_text: Mapped[str | None] = mapped_column(Text)
    signed_name: Mapped[str | None] = mapped_column(String(200))
    signature_ip: Mapped[str | None] = mapped_column(String(64))
    signature_user_agent: Mapped[str | None] = mapped_column(String(400))

    case: Mapped[Case] = relationship(back_populates="authorizations")


class CaseEvidence(TimestampMixin, Base):
    __tablename__ = "case_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    evidence_type: Mapped[str] = mapped_column(String(80))  # "receipt", "boarding_pass", ...
    encrypted_storage_reference: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="customer_upload")

    case: Mapped[Case] = relationship(back_populates="evidence")


class Conversation(TimestampMixin, Base):
    """One thread on one channel with one counterparty.

    Owns thread continuity: channel adapters translate provider threading
    (Gmail threadId, call SID, websocket session) into this row.
    """

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    channel: Mapped[str] = mapped_column(String(20))
    counterparty: Mapped[str] = mapped_column(String(20))  # "company" | "customer"
    support_channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("support_channels.id"))
    provider_thread_id: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(default=True)

    case: Mapped[Case] = relationship(back_populates="conversations")
    communications: Mapped[list["Communication"]] = relationship(back_populates="conversation")

    __table_args__ = (Index("ix_conversations_provider_thread", "provider_thread_id"),)


class Communication(TimestampMixin, Base):
    """Every message on any channel, in either direction."""

    __tablename__ = "communications"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    channel: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(10))
    counterparty: Mapped[str] = mapped_column(String(20))
    provider_message_id: Mapped[str | None] = mapped_column(String(500))
    subject: Mapped[str | None] = mapped_column(String(1000))
    body: Mapped[str] = mapped_column(Text)
    content_reference: Mapped[str | None] = mapped_column(String(500))  # object storage for large/raw
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    delivery_status: Mapped[str | None] = mapped_column(String(40))
    # Structured interpretation produced by the (tool-less) reply classifier.
    classification: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)

    conversation: Mapped[Conversation] = relationship(back_populates="communications")

    __table_args__ = (
        Index("ix_communications_case", "case_id"),
        UniqueConstraint("channel", "provider_message_id", name="uq_comm_provider_message"),
    )


class AgentAction(TimestampMixin, Base):
    """A proposed action, the policy verdict on it, and its execution record."""

    __tablename__ = "agent_actions"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    action_type: Mapped[str] = mapped_column(String(60))
    proposed_action: Mapped[dict[str, Any]] = mapped_column(JSONVariant)
    policy_decision: Mapped[str | None] = mapped_column(String(20))  # PolicyDecisionType
    policy_reasons: Mapped[list[str]] = mapped_column(JSONVariant, default=list)
    execution_status: Mapped[str] = mapped_column(String(30), default=ExecutionStatus.PROPOSED.value)
    approved_by_user_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    model_version: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (Index("ix_agent_actions_case", "case_id"),)


class ScheduledJob(TimestampMixin, Base):
    """Durable timers: follow-ups, inbound polls, deadline checks."""

    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id"))
    job_type: Mapped[str] = mapped_column(String(60))  # "follow_up", "poll_inbound", ...
    payload: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    run_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(default=0)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    locked_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(300), unique=True)

    __table_args__ = (Index("ix_scheduled_jobs_due", "status", "run_at"),)


class OutboxMessage(TimestampMixin, Base):
    """Transactional outbox: the only path to an external send.

    The row is written in the same transaction as the decision to send;
    a worker claims it atomically and delivers exactly once per
    idempotency_key.
    """

    __tablename__ = "outbox_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    agent_action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_actions.id"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    channel: Mapped[str] = mapped_column(String(20))
    recipient_address: Mapped[str] = mapped_column(String(500))  # resolved from SupportChannel
    subject: Mapped[str | None] = mapped_column(String(1000))
    body: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=OutboxStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(default=0)
    locked_by: Mapped[str | None] = mapped_column(String(100))
    locked_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(500))
    provider_thread_id: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_outbox_claimable", "status", "created_at"),)


class RecoveryOutcome(TimestampMixin, Base):
    __tablename__ = "recovery_outcomes"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    recovery_type: Mapped[str] = mapped_column(String(40))  # "cash", "credit", "voucher", "fee_waiver"
    amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    binding: Mapped[bool] = mapped_column(default=False)
    verification_status: Mapped[str] = mapped_column(
        String(40), default=VerificationStatus.UNVERIFIED.value
    )
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # Fee attribution: success fees apply to recoveries obtained as a result
    # of KarenBot's outreach, including when the company settles directly
    # with the customer to bypass the agent (see docs/legal-risk.md §1.1).
    # Values: karenbot_outreach | direct_company_contact | unknown.
    attribution: Mapped[str] = mapped_column(String(40), default="karenbot_outreach")
    notes: Mapped[str | None] = mapped_column(Text)


class BillingRecord(TimestampMixin, Base):
    __tablename__ = "billing_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    pricing_plan: Mapped[str] = mapped_column(String(40))
    fee_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2))
    fee_basis: Mapped[str | None] = mapped_column(String(200))
    payment_status: Mapped[str] = mapped_column(String(40), default="not_charged")


class BankConnection(TimestampMixin, Base):
    """A linked bank/card account (Plaid item). Access tokens are stored
    Fernet-encrypted, same as email OAuth tokens."""

    __tablename__ = "bank_connections"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(40), default="plaid")
    item_id: Mapped[str] = mapped_column(String(200))
    institution_name: Mapped[str | None] = mapped_column(String(200))
    encrypted_access_token: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(40), default="active")
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "provider", "item_id"),)


class RecurringCharge(TimestampMixin, Base):
    """A detected recurring bill/subscription on a linked account."""

    __tablename__ = "recurring_charges"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    bank_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_connections.id"))
    merchant_name: Mapped[str] = mapped_column(String(200))
    normalized_merchant: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    cadence: Mapped[str] = mapped_column(String(20))  # weekly | monthly | yearly
    first_seen: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    occurrences: Mapped[int] = mapped_column(default=0)
    # detected -> (case_created | dismissed); canceled once confirmed gone.
    status: Mapped[str] = mapped_column(String(30), default="detected")
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id"))

    __table_args__ = (
        UniqueConstraint(
            "user_id", "normalized_merchant", "cadence", name="uq_recurring_user_merchant"
        ),
    )


class SystemControl(TimestampMixin, Base):
    """Operational switches (e.g. the global kill switch). Keyed KV so new
    controls don't need migrations; every change is audited by the caller."""

    __tablename__ = "system_controls"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)


class AuditEvent(Base):
    """Append-only audit trail. Never updated, never deleted."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str | None] = mapped_column(String(100))
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_audit_events_case", "case_id", "timestamp"),)

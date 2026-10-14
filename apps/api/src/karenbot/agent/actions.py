"""The ProposedAction contract.

This union is the ONLY shape in which the model can ask the system to do
anything. The model proposes; the policy engine decides; the executor acts.
Models never supply raw recipient addresses — only verified support-channel
ids — and never execute side effects themselves.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from karenbot.domain.enums import Channel
from karenbot.domain.fingerprint import message_fingerprint

RiskLevel = Literal["low", "medium", "high"]


class ActionBase(BaseModel):
    case_id: uuid.UUID
    purpose: str
    risk_level: RiskLevel = "low"


class SendMessage(ActionBase):
    action: Literal["send_message"] = "send_message"
    channel: Channel = Channel.EMAIL
    support_channel_id: uuid.UUID
    subject: str | None = None
    body: str
    claim_type: str
    requested_amount: Decimal | None = None
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    is_follow_up: bool = False
    in_reply_to_communication_id: uuid.UUID | None = None

    def fingerprint(self) -> str:
        """Content fingerprint used for duplicate detection."""
        return message_fingerprint(self.subject, self.body)


class RequestCustomerInfo(ActionBase):
    action: Literal["request_customer_info"] = "request_customer_info"
    questions: list[str]


class ScheduleFollowUp(ActionBase):
    action: Literal["schedule_follow_up"] = "schedule_follow_up"
    run_at: datetime
    note: str | None = None


class RecordOffer(ActionBase):
    action: Literal["record_offer"] = "record_offer"
    offer_type: Literal["cash", "credit", "voucher", "fee_waiver", "other"]
    amount: Decimal | None = None
    currency: str = "USD"
    binding: bool = False
    source_communication_id: uuid.UUID | None = None


class AcceptOffer(ActionBase):
    """Accepting is sensitive: binding terms always require customer approval."""

    action: Literal["accept_offer"] = "accept_offer"
    recovery_outcome_id: uuid.UUID
    binding: bool = True
    risk_level: RiskLevel = "high"


class DraftForCustomer(ActionBase):
    """Respect-the-refusal mode: when a company will only deal with the
    customer directly, KarenBot stops agent-sent outreach and instead drafts
    a message for the customer to send personally. The draft is written in
    the customer's own voice (they are genuinely the sender)."""

    action: Literal["draft_for_customer"] = "draft_for_customer"
    subject: str
    body: str
    guidance: str | None = None  # where/how the customer should send it


class RecommendEscalation(ActionBase):
    action: Literal["recommend_escalation"] = "recommend_escalation"
    target_support_channel_id: uuid.UUID
    reason: str


class CloseCase(ActionBase):
    action: Literal["close_case"] = "close_case"
    outcome: Literal["resolved", "unsuccessful"]
    reason: str


ProposedAction = Annotated[
    SendMessage
    | RequestCustomerInfo
    | ScheduleFollowUp
    | RecordOffer
    | AcceptOffer
    | DraftForCustomer
    | RecommendEscalation
    | CloseCase,
    Field(discriminator="action"),
]

# Action types that always require explicit, separate customer approval,
# regardless of any other check. Mirrors the handoff's sensitive-action list.
SENSITIVE_ACTION_TYPES: frozenset[str] = frozenset({"accept_offer"})

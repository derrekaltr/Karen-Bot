"""Structured outputs the LLM must produce, per task.

Each task's output is a constrained schema — the model cannot return free
text into the pipeline. The reply interpreter in particular runs tool-less
and can only emit this classification shape.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class IntakeResult(BaseModel):
    facts: dict[str, str] = Field(default_factory=dict)
    missing_info: list[str] = Field(default_factory=list)
    suggested_claim_type: str
    incident_summary: str
    # The amount the customer appears to be owed, extracted from their own
    # words (never invented). None when they didn't state one.
    inferred_requested_amount: Decimal | None = None


class EmailDraft(BaseModel):
    subject: str
    body: str


ReplyKind = Literal[
    "offer",
    "denial",
    "request_evidence",
    "acknowledgement",
    "acceptance_confirmation",
    # The company states it will only deal with the customer directly.
    # Triggers respect-the-refusal mode: agent outreach stops for this
    # company; KarenBot drafts messages for the customer to send personally.
    "third_party_refusal",
    "other",
]


class ReplyInterpretation(BaseModel):
    classification: ReplyKind
    offer_amount: Decimal | None = None
    offer_type: Literal["cash", "credit", "voucher", "fee_waiver", "other"] | None = None
    binding: bool = False
    summary: str
    # Set when the inbound content attempted to instruct the agent; such
    # content is flagged, never obeyed.
    suspected_injection: bool = False

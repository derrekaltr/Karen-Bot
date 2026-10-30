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


class ResearchedEvent(BaseModel):
    """One public incident where a published policy owes affected customers.

    Produced by the research_events task from web search results. Everything
    here is a DRAFT for human review in /admin — never published directly.
    """

    company_name: str
    title: str
    # ISO dates as strings so the scripted client and web-derived output
    # share one shape; the research service parses and validates them.
    event_date: str
    region: str | None = None
    summary: str
    entitlement: str
    eligibility: str
    how_to_claim: str
    claim_deadline: str | None = None
    # Claim-type key from our catalog, e.g. "outage_credit".
    category: str
    source_urls: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    notes: str | None = None


class ResearchedEvents(BaseModel):
    events: list[ResearchedEvent] = Field(default_factory=list)

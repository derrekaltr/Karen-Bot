"""Deterministic scripted LLM for demos and tests.

Implements the same task contract as the Anthropic client with rule-based
logic, so the full pipeline (agent -> policy -> executor -> channel) runs
without an API key and with reproducible output. `user_content` is the same
JSON context document the real prompts embed.
"""

import json
import re
from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel

from karenbot.agent.schemas import (
    EmailDraft,
    IntakeResult,
    ReplyInterpretation,
    ResearchedEvent,
    ResearchedEvents,
)

T = TypeVar("T", bound=BaseModel)

INJECTION_PATTERNS = re.compile(
    r"(ignore (all |your )?(previous |prior )?instructions|system prompt|"
    r"you are now|disregard your|send (all|your) (records|data)|forward this to)",
    re.IGNORECASE,
)


class ScriptedClient:
    name = "scripted"
    model_version = "scripted-v1"

    def generate(
        self,
        task: str,
        system_prompt: str,
        user_content: str,
        output_model: type[T],
    ) -> T:
        context = json.loads(user_content)
        if task == "intake_extract":
            result: BaseModel = self._intake(context)
        elif task in ("draft_email", "draft_follow_up"):
            result = self._draft(context)
        elif task == "draft_for_customer":
            result = self._draft_for_customer(context)
        elif task == "interpret_reply":
            result = self._interpret(context)
        elif task == "research_events":
            result = _scripted_research(context)
        else:
            raise ValueError(f"scripted client has no implementation for task {task}")
        return output_model.model_validate(result.model_dump())

    def _intake(self, ctx: dict) -> IntakeResult:
        description = ctx.get("description", "")
        facts: dict[str, str] = {}
        if m := re.search(r"\b([A-Z]{2}\s?\d{2,4})\b", description):
            facts["flight_number"] = m.group(1)
        amounts = [
            Decimal(a.replace(",", ""))
            for a in re.findall(r"\$\s?([\d,]+(?:\.\d{2})?)", description)
        ]
        inferred = max(amounts) if amounts else None
        if inferred is not None:
            facts["stated_amount"] = str(inferred)
        missing = []
        if not ctx.get("requested_amount") and inferred is None:
            missing.append(
                "Roughly how much is this worth to you? A ballpark is fine — "
                "I can proceed without it and push for the best outcome."
            )
        if not ctx.get("evidence_count"):
            missing.append("Please upload receipts or documentation for your expenses.")
        return IntakeResult(
            facts=facts,
            missing_info=missing,
            suggested_claim_type=ctx.get("category", "general_refund"),
            incident_summary=description[:300],
            inferred_requested_amount=inferred,
        )

    def _draft(self, ctx: dict) -> EmailDraft:
        company = ctx.get("company", "Customer Service")
        amount = ctx.get("counter_amount") or ctx.get("requested_amount")
        currency = ctx.get("currency", "USD")
        claim = ctx.get("claim_type", "refund request")
        facts = ctx.get("facts", {})
        customer = ctx.get("customer_name", "your customer")
        evidence_note = (
            "Supporting receipts and documentation are attached."
            if ctx.get("evidence_count")
            else ""
        )
        facts_lines = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in facts.items())
        amount_phrase = f"{currency} {amount}" if amount else "a fair resolution"
        disclosure = ctx.get("disclosure_line") or (
            f"I am writing on behalf of {customer}, who has authorized this correspondence."
        )
        signoff = ctx.get("signoff") or f"Authorized representative for {customer}"
        if ctx.get("acceptance_amount"):
            accepted = f"{currency} {ctx['acceptance_amount']}"
            subject = f"Re: {claim.replace('_', ' ').title()} — offer accepted"
            body = (
                f"Hello {company} support,\n\n"
                f"Thank you for your offer. On behalf of {customer}, we accept "
                f"the offer of {accepted}. Receipts and supporting documentation "
                f"are available and can be provided on request.\n\n"
                f"Please confirm processing and the expected timeline for the "
                f"payment to reach the original form of payment.\n\n"
                f"{disclosure}\n\n"
                f"Kind regards,\n{signoff}"
            )
            return EmailDraft(subject=subject, body=body.strip())
        if ctx.get("is_follow_up"):
            subject = f"Re: {claim.replace('_', ' ').title()} — follow-up"
            body = (
                f"Hello {company} support,\n\n"
                f"I am following up on behalf of {customer} regarding the pending "
                f"{claim.replace('_', ' ')}.\n\n"
                + (
                    f"The previously offered amount does not reflect the documented expenses. "
                    f"Based on the evidence provided and your published policy, we request "
                    f"{amount_phrase}.\n\n"
                    if amount
                    else "We would appreciate an update on the status of this request.\n\n"
                )
                + f"{evidence_note}\n\n"
                f"{disclosure}\n\n"
                f"Kind regards,\n{signoff}"
            )
        else:
            title = claim.replace("_", " ").title()
            subject = f"{title} — request for {currency} {amount}" if amount else title
            policy_summary = ctx.get("policy_summary")
            if policy_summary:
                ask_line = (
                    f"Per your published policy ({policy_summary}), "
                    f"we request reimbursement of {amount_phrase}."
                )
            else:
                # Goodwill basis: never assert a policy or entitlement that
                # does not exist.
                ask_line = (
                    f"Given the documented circumstances, we are requesting "
                    f"{amount_phrase}, which we hope you will consider as a "
                    f"matter of customer goodwill."
                )
            body = (
                f"Hello {company} support,\n\n"
                f"I am writing on behalf of {customer}, with their documented "
                f"authorization, regarding the following matter:\n\n"
                f"{ctx.get('incident_summary', '')}\n\n"
                f"{facts_lines}\n\n"
                f"{ask_line} {evidence_note}\n\n"
                f"{disclosure}\n\n"
                f"Kind regards,\n{signoff}"
            )
        return EmailDraft(subject=subject, body=body.strip())

    def _draft_for_customer(self, ctx: dict) -> EmailDraft:
        """First-person draft the customer sends themselves (no KarenBot
        disclosure — the customer is genuinely the sender)."""
        company = ctx.get("company", "Customer Service")
        amount = ctx.get("requested_amount")
        currency = ctx.get("currency", "USD")
        claim = ctx.get("claim_type", "refund request")
        facts_lines = "\n".join(
            f"- {k.replace('_', ' ')}: {v}" for k, v in ctx.get("facts", {}).items()
        )
        if "cancellation" in claim:
            subject = f"Cancellation request — {company}"
            ask = (
                "I am writing to cancel my subscription/membership, effective "
                "immediately. Please confirm the cancellation in writing, stop "
                "all future charges to my payment method, and let me know if any "
                "final steps are required on my side."
            )
        elif "negotiation" in claim:
            subject = f"Request to review my current rate — {company}"
            ask = (
                "I have been a paying customer and am reviewing my recurring "
                "expenses. I would like to ask whether a lower rate, a smaller "
                "plan, or any current promotion can be applied to my account. "
                "If not, please let me know my options, including cancellation."
            )
        else:
            subject = f"{claim.replace('_', ' ').title()} — request for {currency} {amount}"
            ask = (
                f"Per your published policy "
                f"({ctx.get('policy_summary', 'customer service policy')}), I am "
                f"requesting reimbursement of {currency} {amount}. I can provide "
                "receipts and documentation on request."
            )
        body = (
            f"Hello {company} support,\n\n"
            f"I am writing about the following matter:\n\n"
            f"{ctx.get('incident_summary', '')}\n\n"
            f"{facts_lines}\n\n"
            f"{ask}\n\n"
            "Kind regards"
        )
        return EmailDraft(subject=subject, body=body.strip())

    def _interpret(self, ctx: dict) -> ReplyInterpretation:
        body = ctx.get("body", "")
        suspected = bool(INJECTION_PATTERNS.search(body))
        amount: Decimal | None = None
        if m := re.search(r"\$\s?(\d+(?:\.\d{2})?)", body):
            amount = Decimal(m.group(1))

        lowered = body.lower()
        if re.search(
            r"(only (deal|work|correspond|communicate) (directly )?with (the )?(customer|account holder|passenger)|"
            r"directly (from|with) the (customer|account holder)|"
            r"unable to (work|correspond) with third[- ]part)",
            lowered,
        ):
            kind = "third_party_refusal"
        elif re.search(r"(has been (approved|issued|processed)|refund (was|has been) sent)", lowered) and amount:
            kind = "acceptance_confirmation"
        elif re.search(r"(we can offer|offer you|willing to (provide|refund)|as a goodwill)", lowered):
            kind = "offer"
        elif re.search(r"(unable to|cannot|denied|must decline|not eligible)", lowered):
            kind = "denial"
        elif re.search(r"(provide (receipts|documentation)|send us (proof|receipts))", lowered):
            kind = "request_evidence"
        elif re.search(r"(received your (message|request)|looking into|case number)", lowered):
            kind = "acknowledgement"
        else:
            kind = "other"

        offer_type = None
        binding = False
        if kind == "offer":
            offer_type = "voucher" if "voucher" in lowered or "credit" in lowered else "cash"
            binding = "final" in lowered or "settlement" in lowered or "full and final" in lowered
        return ReplyInterpretation(
            classification=kind,  # type: ignore[arg-type]
            offer_amount=amount if kind in ("offer", "acceptance_confirmation") else None,
            offer_type=offer_type,  # type: ignore[arg-type]
            binding=binding,
            summary=body[:200],
            suspected_injection=suspected,
        )


def _scripted_research(ctx: dict) -> ResearchedEvents:
    """One deterministic canned event, dated inside the lookback window."""
    from datetime import UTC, datetime, timedelta

    event_date = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    deadline = (datetime.now(UTC) + timedelta(days=29)).date().isoformat()
    return ResearchedEvents(
        events=[
            ResearchedEvent(
                company_name="AT&T",
                title="Scripted: regional fiber outage",
                event_date=event_date,
                region="Southeast US",
                summary="A scripted multi-hour fiber outage used in tests.",
                entitlement="A full day's bill credit under the AT&T Guarantee.",
                eligibility="Fiber customers in the affected region during the outage.",
                how_to_claim="Redeem via the link AT&T emails within 30 days.",
                claim_deadline=deadline,
                category="outage_credit",
                source_urls=["https://example.com/scripted-outage"],
                confidence="high",
                notes="scripted fixture",
            )
        ]
    )

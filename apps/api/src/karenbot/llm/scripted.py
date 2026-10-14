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

from karenbot.agent.schemas import EmailDraft, IntakeResult, ReplyInterpretation

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
        else:
            raise ValueError(f"scripted client has no implementation for task {task}")
        return output_model.model_validate(result.model_dump())

    def _intake(self, ctx: dict) -> IntakeResult:
        description = ctx.get("description", "")
        facts: dict[str, str] = {}
        if m := re.search(r"\b([A-Z]{2}\s?\d{2,4})\b", description):
            facts["flight_number"] = m.group(1)
        if m := re.search(r"\$\s?(\d+(?:\.\d{2})?)", description):
            facts["claimed_expenses"] = m.group(1)
        missing = []
        if not ctx.get("requested_amount"):
            missing.append("What total amount are you requesting?")
        if not ctx.get("evidence_count"):
            missing.append("Please upload receipts or documentation for your expenses.")
        return IntakeResult(
            facts=facts,
            missing_info=missing,
            suggested_claim_type=ctx.get("category", "general_refund"),
            incident_summary=description[:300],
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
        if ctx.get("is_follow_up"):
            subject = f"Re: {claim.replace('_', ' ').title()} — follow-up"
            body = (
                f"Hello {company} support,\n\n"
                f"I am following up on behalf of {customer} regarding the pending "
                f"{claim.replace('_', ' ')}.\n\n"
                + (
                    f"The previously offered amount does not reflect the documented expenses. "
                    f"Based on the evidence provided and your published policy, we request "
                    f"{currency} {amount}.\n\n"
                    if amount
                    else "We would appreciate an update on the status of this request.\n\n"
                )
                + f"{evidence_note}\n\n"
                "This message was sent by KarenBot, an authorized representative acting "
                f"with the documented consent of {customer}.\n\n"
                "Kind regards,\nKarenBot on behalf of the customer"
            )
        else:
            subject = f"{claim.replace('_', ' ').title()} — request for {currency} {amount}"
            body = (
                f"Hello {company} support,\n\n"
                f"I am writing on behalf of {customer}, with their documented "
                f"authorization, regarding the following matter:\n\n"
                f"{ctx.get('incident_summary', '')}\n\n"
                f"{facts_lines}\n\n"
                f"Per your published policy ({ctx.get('policy_summary', 'customer service policy')}), "
                f"we request reimbursement of {currency} {amount}. {evidence_note}\n\n"
                "This message was sent by KarenBot, an authorized representative acting "
                f"with the documented consent of {customer}.\n\n"
                "Kind regards,\nKarenBot on behalf of the customer"
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
        subject = f"{claim.replace('_', ' ').title()} — request for {currency} {amount}"
        body = (
            f"Hello {company} support,\n\n"
            f"I am writing about the following matter:\n\n"
            f"{ctx.get('incident_summary', '')}\n\n"
            f"{facts_lines}\n\n"
            f"Per your published policy "
            f"({ctx.get('policy_summary', 'customer service policy')}), I am "
            f"requesting reimbursement of {currency} {amount}. I can provide "
            "receipts and documentation on request.\n\n"
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

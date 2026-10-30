"""Agent runtime: proposes actions; never executes them directly.

Every step is: build context -> (maybe) call the LLM for a constrained,
structured output -> persist a ProposedAction -> policy evaluation ->
executor. Negotiation decisions that must be deterministic (accept vs
counter thresholds, escalation triggers) are plain code here, not model
output.
"""

import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.agent import prompts
from karenbot.agent.actions import (
    AcceptOffer,
    DraftForCustomer,
    ProposedAction,
    RecordOffer,
    RequestCustomerInfo,
    SendMessage,
)
from karenbot.agent.eligibility import EligibilityResult, assess
from karenbot.agent.schemas import EmailDraft, IntakeResult, ReplyInterpretation
from karenbot.domain.enums import (
    ActorType,
    CaseEvent,
    CaseStatus,
    PolicyDecisionType,
)
from karenbot.domain.models import (
    AgentAction,
    AuditEvent,
    Case,
    CaseEvidence,
    Communication,
    CompanyPolicy,
    RecoveryOutcome,
    SupportChannel,
)
from karenbot.domain.state_machine import transition
from karenbot.llm.base import LLMClient
from karenbot.policy.context import build_case_context
from karenbot.policy.engine import PolicyDecision, evaluate
from karenbot.workflows import executor

# Categories whose cases are instructions (cancel/negotiate a bill) rather
# than compensation claims; drafting and resolution differ. Mirrors
# discovery.service ACTION_CATEGORIES (string literals to avoid an import
# cycle).
CANCELLATION_CATEGORY = "subscription_cancellation"
BILL_NEGOTIATION_CATEGORY = "bill_negotiation"


def case_intent(case: "Case") -> str:
    if case.category == CANCELLATION_CATEGORY:
        return "cancellation"
    if case.category == BILL_NEGOTIATION_CATEGORY:
        return "bill_negotiation"
    return "recovery"


# Deterministic negotiation rule: accept offers at or above this fraction of
# the requested amount; counter below it.
ACCEPT_RATIO = Decimal("0.8")


class AgentRuntime:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    # ---- helpers ---------------------------------------------------------

    def _propose(
        self, session: Session, action: ProposedAction, prompt_version: str | None = None
    ) -> tuple[AgentAction, PolicyDecision]:
        row = executor.record_proposal(
            session,
            action,
            model_version=self.llm.model_version,
            prompt_version=prompt_version,
        )
        case = session.get(Case, action.case_id)
        assert case is not None
        ctx = build_case_context(session, case)
        decision = evaluate(action, ctx)
        executor.apply_decision(session, row, action, decision)
        return row, decision

    def _generate(self, task: str, context: dict, output_model):
        prompt_text, version = prompts.load_prompt(task)
        result = self.llm.generate(
            task, prompt_text, json.dumps(context, default=str), output_model
        )
        return result, version

    def _case_context_doc(self, session: Session, case: Case) -> dict:
        evidence = session.scalars(
            select(CaseEvidence).where(CaseEvidence.case_id == case.id)
        ).all()
        # Only the policy matching THIS claim type may be cited in drafts;
        # goodwill requests carry no policy summary at all.
        policy = next(
            (
                p
                for p in session.scalars(
                    select(CompanyPolicy).where(
                        CompanyPolicy.company_id == case.company_id,
                        CompanyPolicy.verified_at.is_not(None),
                    )
                )
                if (p.eligibility_rules or {}).get("claim_type") == case.category
            ),
            None,
        )
        return {
            "company": case.company.name,
            "category": case.category,
            "case_intent": case_intent(case),
            "claim_type": case.category,
            "description": case.description,
            "incident_summary": (case.facts or {}).get("incident_summary", case.description),
            "facts": case.facts or {},
            "requested_amount": str(case.requested_amount) if case.requested_amount else None,
            "currency": case.currency,
            "evidence_count": len(evidence),
            "policy_summary": (policy.content or {}).get("summary") if policy else None,
            "basis": case.eligibility_basis,
            "customer_name": case.user.display_name or "the customer",
            **self._disclosure(case),
        }

    @staticmethod
    def _disclosure(case: Case) -> dict:
        """Representation disclosure wording. Default mode avoids the brand
        string (a trivially filterable blocklist key) while still disclosing
        the agency relationship; prompts separately enforce that automation
        is never denied if asked. Wording is on the attorney checklist."""
        from karenbot.config import get_settings

        customer = case.user.display_name or "the customer"
        if get_settings().disclosure_mode == "branded":
            line = (
                f"This message is sent by KarenBot, an authorized representative "
                f"acting with the documented consent of {customer}."
            )
            signoff = f"KarenBot\nAuthorized representative of {customer}"
        else:
            line = (
                f"I am Karen, writing as an authorized representative of "
                f"{customer}, who has authorized this correspondence."
            )
            signoff = f"Karen\nAuthorized representative for {customer}"
        return {
            "disclosure_instruction": (
                f"Open with this exact representation disclosure: \"{line}\" "
                f"Sign off exactly as: \"{signoff}\""
            ),
            "disclosure_line": line,
            "signoff": signoff,
        }

    # ---- pipeline steps --------------------------------------------------

    def run_intake(self, session: Session, case: Case) -> IntakeResult:
        result, version = self._generate(
            "intake_extract", self._case_context_doc(session, case), IntakeResult
        )
        case.facts = {
            **(case.facts or {}),
            **result.facts,
            "incident_summary": result.incident_summary,
        }
        # The intake form no longer asks for an amount; adopt the one the
        # customer stated in their own words, if any.
        if case.requested_amount is None and result.inferred_requested_amount is not None:
            case.requested_amount = result.inferred_requested_amount
            case.facts = {**case.facts, "amount_source": "stated_in_description"}
        if result.missing_info:
            self._propose(
                session,
                RequestCustomerInfo(
                    case_id=case.id,
                    purpose="collect_missing_case_details",
                    questions=result.missing_info,
                ),
                prompt_version=version,
            )
        else:
            transition(session, case, CaseEvent.INTAKE_COMPLETE, actor_type=ActorType.AGENT)
        return result

    def complete_intake(self, session: Session, case: Case) -> None:
        """Customer supplied missing info; move to eligibility review."""
        transition(session, case, CaseEvent.INFO_RECEIVED, actor_type=ActorType.CUSTOMER)

    def assess_eligibility(self, session: Session, case: Case) -> EligibilityResult:
        result = assess(session, case)
        session.add(
            AuditEvent(
                actor_type=ActorType.AGENT.value,
                case_id=case.id,
                event_type="eligibility.assessed",
                event_payload={
                    "eligible": result.eligible,
                    "basis": result.basis,
                    "policy_id": result.policy_id,
                    "reasons": result.reasons,
                },
            )
        )
        if result.eligible:
            case.eligibility_basis = result.basis
            transition(session, case, CaseEvent.ELIGIBILITY_CONFIRMED, actor_type=ActorType.AGENT)
        else:
            transition(session, case, CaseEvent.ELIGIBILITY_REJECTED, actor_type=ActorType.AGENT)
        return result

    def initiate_contact(self, session: Session, case: Case) -> PolicyDecision:
        if case.contact_mode == "assist":
            return self._initiate_assist(session, case)
        channel = self._primary_channel(session, case)
        draft, version = self._generate(
            "draft_email", self._case_context_doc(session, case), EmailDraft
        )
        evidence_ids = list(
            session.scalars(select(CaseEvidence.id).where(CaseEvidence.case_id == case.id)).all()
        )
        action = SendMessage(
            case_id=case.id,
            purpose=f"initial_{case.category}_request",
            support_channel_id=channel.id,
            subject=draft.subject,
            body=draft.body,
            claim_type=case.category,
            requested_amount=case.requested_amount,
            evidence_ids=evidence_ids,
        )
        _, decision = self._propose(session, action, prompt_version=version)
        return decision

    def _initiate_assist(self, session: Session, case: Case) -> PolicyDecision:
        """Assist mode: draft the message in the customer's own voice; the
        customer sends it. Used for non-targetable merchants (moral code).
        Idempotent: one prepared draft per case purpose."""
        existing = session.scalars(
            select(AgentAction).where(
                AgentAction.case_id == case.id,
                AgentAction.action_type == "draft_for_customer",
                AgentAction.execution_status == "executed",
            )
        ).first()
        if existing is not None:
            return PolicyDecision(PolicyDecisionType.ALLOW, ["draft_already_prepared"])
        company = case.company
        context = {
            **self._case_context_doc(session, case),
            "for_customer_sending": True,
        }
        draft, version = self._generate("draft_for_customer", context, EmailDraft)
        where = (
            f"the billing/support contact listed on {company.website}"
            if company.website
            else f"{company.name}'s billing or support contact (check a recent "
            "charge statement, receipt, or their website)"
        )
        action = DraftForCustomer(
            case_id=case.id,
            purpose=f"assist_{case.category}",
            subject=draft.subject,
            body=draft.body,
            guidance=(
                f"{company.name} isn't a company KarenBot contacts directly, so "
                f"this message is written for you to send yourself. Send it from "
                f"your own email to {where}. Paste their reply here and I'll help "
                "with the next step."
            ),
        )
        _, decision = self._propose(session, action, prompt_version=version)
        return decision

    def handle_company_reply(
        self, session: Session, case: Case, comm: Communication
    ) -> ReplyInterpretation:
        interpretation, version = self._generate(
            "interpret_reply",
            {"subject": comm.subject, "body": comm.body},
            ReplyInterpretation,
        )
        comm.classification = {
            **(comm.classification or {}),
            **interpretation.model_dump(mode="json"),
        }
        if interpretation.suspected_injection:
            session.add(
                AuditEvent(
                    actor_type=ActorType.SYSTEM.value,
                    case_id=case.id,
                    event_type="security.suspected_injection",
                    event_payload={"communication_id": str(comm.id)},
                )
            )

        kind = interpretation.classification
        if kind == "offer":
            self._handle_offer(session, case, interpretation, version)
        elif kind == "request_evidence":
            self._send_follow_up(
                session, case, version, note="provide_requested_evidence", counter_amount=None
            )
        elif kind == "denial":
            self._handle_denial(session, case, version)
        elif kind == "acceptance_confirmation":
            if case_intent(case) == "cancellation":
                self._complete_cancellation(session, case)
            else:
                self._mark_company_confirmed(session, case)
        elif kind == "third_party_refusal":
            self._enter_respect_the_refusal_mode(session, case, version)
        # acknowledgement / other: wait; the scheduler owns follow-up timing.
        return interpretation

    # ---- internals -------------------------------------------------------

    def _primary_channel(self, session: Session, case: Case) -> SupportChannel:
        channel = session.scalars(
            select(SupportChannel).where(
                SupportChannel.company_id == case.company_id,
                SupportChannel.verified.is_(True),
                SupportChannel.active.is_(True),
                SupportChannel.is_escalation.is_(False),
            )
        ).first()
        if channel is None:
            raise RuntimeError("no verified support channel for company")
        return channel

    def _handle_offer(
        self,
        session: Session,
        case: Case,
        interpretation: ReplyInterpretation,
        prompt_version: str,
    ) -> None:
        self._propose(
            session,
            RecordOffer(
                case_id=case.id,
                purpose="record_company_offer",
                offer_type=interpretation.offer_type or "other",
                amount=interpretation.offer_amount,
                binding=interpretation.binding,
            ),
            prompt_version=prompt_version,
        )
        requested = case.requested_amount or Decimal("0")
        offered = interpretation.offer_amount or Decimal("0")
        acceptable = requested > 0 and offered >= requested * ACCEPT_RATIO
        # No target amount on the case: Karen can't judge adequacy, so any
        # concrete offer goes to the customer for the call (the AcceptOffer
        # proposal is approval-gated, surfacing it in the UI).
        if requested == 0 and offered > 0:
            acceptable = True

        if acceptable:
            outcome = session.scalars(
                select(RecoveryOutcome)
                .where(RecoveryOutcome.case_id == case.id)
                .order_by(RecoveryOutcome.created_at.desc())
            ).first()
            assert outcome is not None
            row, decision = self._propose(
                session,
                AcceptOffer(
                    case_id=case.id,
                    purpose="accept_company_offer",
                    recovery_outcome_id=outcome.id,
                    binding=True,
                ),
                prompt_version=prompt_version,
            )
            # Sensitive action: surface the approval to the customer.
            if decision.decision == PolicyDecisionType.NEEDS_APPROVAL:
                transition(
                    session,
                    case,
                    CaseEvent.APPROVAL_REQUESTED,
                    actor_type=ActorType.AGENT,
                    payload={"agent_action_id": str(row.id)},
                )
        else:
            # Counter: decline and restate the documented request.
            transition(session, case, CaseEvent.OFFER_DECLINED, actor_type=ActorType.AGENT)
            self._send_follow_up(
                session,
                case,
                prompt_version,
                note="counter_low_offer",
                counter_amount=case.requested_amount,
            )

    def _handle_denial(self, session: Session, case: Case, prompt_version: str) -> None:
        self._send_follow_up(
            session,
            case,
            prompt_version,
            note="reassert_with_evidence",
            counter_amount=case.requested_amount,
        )

    def _send_follow_up(
        self,
        session: Session,
        case: Case,
        prompt_version: str,
        *,
        note: str,
        counter_amount: Decimal | None,
    ) -> PolicyDecision:
        channel = self._primary_channel(session, case)
        context = {
            **self._case_context_doc(session, case),
            "is_follow_up": True,
            "counter_amount": str(counter_amount) if counter_amount else None,
            "history_summary": note,
        }
        draft, version = self._generate("draft_follow_up", context, EmailDraft)
        action = SendMessage(
            case_id=case.id,
            purpose=note,
            support_channel_id=channel.id,
            subject=draft.subject,
            body=draft.body,
            claim_type=case.category,
            requested_amount=counter_amount,
            is_follow_up=True,
        )
        _, decision = self._propose(session, action, prompt_version=version)
        return decision

    def _enter_respect_the_refusal_mode(
        self, session: Session, case: Case, prompt_version: str
    ) -> None:
        """The company only deals with customers directly. We honor that:
        flag the company (policy engine will deny any further agent sends)
        and draft a message in the customer's own voice for them to send."""
        company = case.company
        if not company.refuses_third_party:
            company.refuses_third_party = True
            session.add(
                AuditEvent(
                    actor_type=ActorType.SYSTEM.value,
                    case_id=case.id,
                    event_type="channel.third_party_refusal_recorded",
                    event_payload={"company_id": str(company.id)},
                )
            )
        channel = self._primary_channel(session, case)
        context = {
            **self._case_context_doc(session, case),
            "for_customer_sending": True,
            "send_to_address": channel.address,
        }
        draft, version = self._generate("draft_for_customer", context, EmailDraft)
        self._propose(
            session,
            DraftForCustomer(
                case_id=case.id,
                purpose="assist_customer_direct_contact",
                subject=draft.subject,
                body=draft.body,
                guidance=(
                    f"{company.name} only works with customers directly, so this "
                    f"email is written for you to send yourself. Send it from your "
                    f"own email to {channel.address}. I'll help you interpret "
                    "their reply."
                ),
            ),
            prompt_version=version,
        )

    def send_acceptance_confirmation(
        self, session: Session, case: Case, amount: Decimal | None
    ) -> PolicyDecision:
        """After the customer approves an offer, tell the company: accepted,
        receipts available, please process. Replies to their latest message,
        so the pacing floor's reply exemption applies."""
        channel = self._primary_channel(session, case)
        context = {
            **self._case_context_doc(session, case),
            "is_follow_up": True,
            "acceptance_amount": str(amount) if amount is not None else None,
            "history_summary": "customer approved the company's offer; confirm acceptance",
        }
        draft, version = self._generate("draft_follow_up", context, EmailDraft)
        action = SendMessage(
            case_id=case.id,
            purpose="accept_offer_confirmation",
            support_channel_id=channel.id,
            subject=draft.subject,
            body=draft.body,
            claim_type=case.category,
            requested_amount=None,
            is_follow_up=False,  # acceptance does not consume follow-up quota
        )
        _, decision = self._propose(session, action, prompt_version=version)
        return decision

    def _complete_cancellation(self, session: Session, case: Case) -> None:
        """Company confirmed the cancellation in writing. Record the outcome
        (annual savings when a linked recurring charge exists) and hand the
        case to the customer to verify the billing actually stopped."""
        from karenbot.domain.models import RecurringCharge

        charge = session.scalars(
            select(RecurringCharge).where(RecurringCharge.case_id == case.id)
        ).first()
        amount = None
        currency = case.currency
        if charge is not None:
            multiplier = {"weekly": 52, "monthly": 12, "yearly": 1}.get(charge.cadence, 12)
            amount = charge.amount * multiplier
            currency = charge.currency
        session.add(
            RecoveryOutcome(
                case_id=case.id,
                recovery_type="subscription_savings",
                amount=amount,
                currency=currency,
                binding=True,
                verification_status="company_confirmed",
            )
        )
        transition(
            session,
            case,
            CaseEvent.CANCELLATION_CONFIRMED,
            actor_type=ActorType.AGENT,
            payload={"annual_savings": str(amount) if amount is not None else None},
        )

    def decline_pending_offer(self, session: Session, case: Case) -> PolicyDecision:
        """After the customer declines an offer (e.g. a retention deal on a
        cancellation case), tell the company and restate the demand."""
        return self._send_follow_up(
            session,
            case,
            "customer_decision",
            note="customer_declined_offer_reassert_request",
            counter_amount=case.requested_amount,
        )

    def _mark_company_confirmed(self, session: Session, case: Case) -> None:
        outcome = session.scalars(
            select(RecoveryOutcome)
            .where(RecoveryOutcome.case_id == case.id)
            .order_by(RecoveryOutcome.created_at.desc())
        ).first()
        if outcome is not None and outcome.verification_status == "unverified":
            outcome.verification_status = "company_confirmed"
        if case.status == CaseStatus.AWAITING_RESPONSE.value:
            # Confirmation arrived while we were waiting; the reply ingest
            # already moved us to NEGOTIATING via REPLY_RECEIVED.
            pass

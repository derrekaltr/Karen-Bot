"""Deterministic eligibility assessment.

The LLM extracts facts; THIS module decides whether a claim is pursued and on
what basis. Rules live as data on CompanyPolicy.eligibility_rules:

    {
      "claim_type": "baggage_delay_expenses",
      "basis": "entitlement" | "goodwill",
      "max_amount": 500,
      "requires_evidence": true
    }
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.domain.models import Case, CaseEvidence, CompanyPolicy


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    basis: str | None  # "entitlement" | "goodwill"
    policy_id: str | None
    reasons: list[str]


# Categories that are intrinsically eligible: a customer always has the
# right to cancel their own subscription, ask for a lower price, or request
# a refund review of their own recurring charges. No company policy needed;
# the basis is the customer's own account relationship, never an entitlement
# claim against the company.
CUSTOMER_RIGHT_CATEGORIES = frozenset(
    {"subscription_cancellation", "bill_negotiation", "recurring_charge_refund"}
)


def assess(session: Session, case: Case) -> EligibilityResult:
    # Assist-mode cases: the customer pursues their own complaint and Karen
    # only drafts. No entitlement is asserted against anyone, so no verified
    # company policy is required.
    if case.contact_mode == "assist":
        return EligibilityResult(
            eligible=True,
            basis="customer_request",
            policy_id=None,
            reasons=["assist_mode_customer_own_complaint"],
        )
    if case.category in CUSTOMER_RIGHT_CATEGORIES:
        return EligibilityResult(
            eligible=True,
            basis="customer_right",
            policy_id=None,
            reasons=["customer_account_relationship"],
        )

    policies = session.scalars(
        select(CompanyPolicy).where(CompanyPolicy.company_id == case.company_id)
    ).all()
    evidence_count = len(
        session.scalars(select(CaseEvidence.id).where(CaseEvidence.case_id == case.id)).all()
    )

    reasons: list[str] = []
    for policy in policies:
        rules = policy.eligibility_rules or {}
        if rules.get("claim_type") != case.category:
            continue
        if policy.verified_at is None:
            reasons.append(f"policy_not_verified:{policy.id}")
            continue
        max_amount = rules.get("max_amount")
        if (
            max_amount is not None
            and case.requested_amount is not None
            and float(case.requested_amount) > float(max_amount)
        ):
            reasons.append(f"requested_amount_exceeds_policy_max:{max_amount}")
            continue
        if rules.get("requires_evidence") and evidence_count == 0:
            reasons.append("evidence_required_but_missing")
            continue
        return EligibilityResult(
            eligible=True,
            basis=rules.get("basis", "goodwill"),
            policy_id=str(policy.id),
            reasons=["matched_verified_policy"],
        )

    if reasons:
        # A policy for this claim type exists but its conditions failed
        # (over the cap, missing required evidence, unverified): reject.
        return EligibilityResult(eligible=False, basis=None, policy_id=None, reasons=reasons)

    # No policy covers this claim type at all. Per the handoff, discretionary
    # goodwill requests are a legitimate agent activity — pursue on a
    # goodwill basis, never asserting entitlement. Policy-backed claims
    # remain the only path to entitlement language.
    return EligibilityResult(
        eligible=True,
        basis="goodwill",
        policy_id=None,
        reasons=["no_matching_policy_goodwill_request"],
    )

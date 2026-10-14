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


def assess(session: Session, case: Case) -> EligibilityResult:
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

    if not reasons:
        reasons.append("no_matching_verified_policy")
    return EligibilityResult(eligible=False, basis=None, policy_id=None, reasons=reasons)

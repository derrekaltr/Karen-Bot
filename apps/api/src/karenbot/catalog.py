"""Production product catalog: the data KarenBot needs to be usable.

Loads REAL companies, their researched (unverified) support channels, the
verified Tier 1 compensation policies, generosity intel, the founding ops
team, and the launch checklist. Strictly no demo data: no fake users, no
.example support channels, no demo events, no test companies.

Idempotent: safe to run repeatedly. Dev's /dev/seed builds on top of this
(adding the demo user, fake verified channels for the simulator, demo
events); production loads it via POST /admin/catalog/load.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.domain.models import (
    Company,
    CompanyPolicy,
    OpsItem,
    OpsMember,
    SupportChannel,
)

# Real enterprises in the curated catalog. Demo companies (Acme Air,
# ALTR Test Airways, Rosa's Corner Bakery) are deliberately absent — they
# exist only in the dev seeder. Tier 1 policy data adds more (AWS, AT&T,
# Marriott, ...) via load below.
PRODUCTION_COMPANIES: list[tuple[str, str]] = [
    ("Chipotle", "restaurant"),
    ("Delta Air Lines", "airline"),
    ("American Airlines", "airline"),
    ("Southwest Airlines", "airline"),
    ("JetBlue", "airline"),
    ("Uber", "rideshare"),
    ("American Express", "financial"),
    ("McDonald's", "restaurant"),
    ("Amazon", "ecommerce"),
]

# Generosity intelligence (docs/research/company-generosity.md).
# INTERNAL TARGETING ONLY — never asserted to companies in negotiation.
COMPANY_INTEL: dict[str, dict[str, Any]] = {
    "American Airlines": {"goodwill_low": 50, "goodwill_high": 300,
        "goodwill_unit": "miles_5k_20k", "best_channel": "customer relations email form",
        "notes": "Miles goodwill well documented; exec emails reported bouncing since 1/2026.",
        "evidence": "JR/FC"},
    "Delta Air Lines": {"goodwill_low": 25, "goodwill_high": 150,
        "goodwill_unit": "miles_2.5k_10k", "best_channel": "live chat, then feedback form",
        "notes": "Proactive 10k miles after cancellations documented; chat beats phone.",
        "evidence": "JR"},
    "Southwest Airlines": {"goodwill_low": 75, "goodwill_high": 300,
        "goodwill_unit": "voucher", "best_channel": "delay form (never automatic)",
        "notes": "$75+ voucher is a DOT-settlement entitlement through Apr 2027 — ask.",
        "evidence": "PG"},
    "JetBlue": {"goodwill_low": 60, "goodwill_high": 60,
        "goodwill_unit": "points_5000", "best_channel": "automatic (attach TrueBlue first)",
        "notes": "Flat 5,000 TrueBlue points for qualifying controllable disruptions.",
        "evidence": "PG"},
    "American Express": {"goodwill_low": 50, "goodwill_high": 700,
        "goodwill_unit": "fee_waiver", "best_channel": "chat/phone — just ask",
        "notes": "Fee-waiver asks succeed ~90% (self-reported); retention offers to 50k pts.",
        "evidence": "JR"},
    "Uber": {"goodwill_low": 5, "goodwill_high": 40,
        "goodwill_unit": "credit", "best_channel": "in-app within 30 days",
        "notes": "Credits over refunds; 'sole discretion' policy.", "evidence": "PG/JR"},
    "Amazon": {"goodwill_low": 10, "goodwill_high": 100,
        "goodwill_unit": "refund", "best_channel": "account chat",
        "notes": "Returnless-refund algorithmic; report early, avoid pattern abuse.",
        "evidence": "INF"},
    "Chipotle": {"goodwill_low": 5, "goodwill_high": 30, "goodwill_unit": "refund_or_bogo",
        "best_channel": "contact form / chat", "notes": "App recovery offers typical.",
        "evidence": "FC"},
    "McDonald's": {"goodwill_low": 5, "goodwill_high": 25, "goodwill_unit": "refund",
        "best_channel": "feedback form", "notes": "Franchisee-dependent.", "evidence": "FC"},
}

FOUNDING_OPS_MEMBERS: list[tuple[str, str, str]] = [
    ("derrekpbrown@gmail.com", "Derrek", "owner"),
    ("derrek@altrmgmt.com", "Derrek (ALTR)", "owner"),
]

LAUNCH_CHECKLIST: list[tuple[str, str]] = [
    (
        "Form the business entity",
        "LLC or C-corp — blocks Stripe, Plaid production, insurance, and the "
        "attorney engagement. See docs/legal-risk.md.",
    ),
    (
        "Attorney review of legal gates",
        "UPL exposure, success-fee structure, LoA wording, disclosure wording, "
        "ToS/privacy policy. docs/legal-risk.md is the brief.",
    ),
    (
        "Stripe account + billing",
        "Requires the entity. Subscription + success-fee billing model.",
    ),
    (
        "Plaid production application",
        "Sandbox is free/instant; production approval is needed to link real "
        "customer banks.",
    ),
    (
        "Google OAuth verification + CASA",
        "Until verified, Gmail connections are testing-mode only (7-day token "
        "expiry, allowlisted users).",
    ),
    (
        "Rotate exposed secrets",
        "Google client secret and Anthropic key passed through chat during "
        "setup — rotate both before production.",
    ),
    (
        "Business insurance quote",
        "E&O / professional liability for a consumer-claims service.",
    ),
    (
        "Privacy policy + terms of service",
        "Blocked on attorney; drafts can start from docs/legal-risk.md.",
    ),
]


def load_research_channels(session: Session, company: Company) -> int:
    """Researched real-world channels as UNVERIFIED rows (the policy engine
    refuses to send until a human verifies each in /admin)."""
    from karenbot.data_support_channels import RESEARCH_CHANNELS

    existing = {
        c.address
        for c in session.scalars(
            select(SupportChannel).where(SupportChannel.company_id == company.id)
        )
    }
    added = 0
    for channel_type, address, purpose, is_escalation, source in RESEARCH_CHANNELS.get(
        company.name, []
    ):
        if address in existing:
            continue
        session.add(
            SupportChannel(
                company_id=company.id,
                channel=channel_type,
                address=address,
                purpose=purpose,
                is_escalation=is_escalation,
                verified=False,
                verification_source_url=source,
            )
        )
        added += 1
    return added


def load_tier1_policies(session: Session) -> int:
    """Tier 1 compensation-policy research (data_compensation_policies).
    PRIMARY-confidence records load verified; others unverified pending
    human review (eligibility ignores unverified policies)."""
    from karenbot.data_compensation_policies import TIER1_COMPANIES

    added = 0
    for name, spec in TIER1_COMPANIES.items():
        company = session.scalars(select(Company).where(Company.name == name)).first()
        if company is None:
            company = Company(name=name, industry=spec["industry"], size_class="enterprise")
            session.add(company)
            session.flush()
        existing = {
            p.policy_type
            for p in session.scalars(
                select(CompanyPolicy).where(CompanyPolicy.company_id == company.id)
            )
        }
        for policy in spec["policies"]:
            if policy["policy_type"] in existing:
                continue
            session.add(
                CompanyPolicy(
                    company_id=company.id,
                    policy_type=policy["policy_type"],
                    source_url=policy["source_url"],
                    verified_at=datetime.now(UTC) if policy["verified"] else None,
                    content={"summary": policy["summary"]},
                    eligibility_rules=policy["rules"],
                )
            )
            added += 1
        load_research_channels(session, company)
    return added


def load_ops_members(session: Session) -> int:
    existing = {m.email for m in session.scalars(select(OpsMember))}
    added = 0
    for email, name, role in FOUNDING_OPS_MEMBERS:
        if email not in existing:
            session.add(
                OpsMember(email=email, display_name=name, role=role, added_by="catalog")
            )
            added += 1
    return added


def load_launch_checklist(session: Session) -> int:
    existing = {
        i.title for i in session.scalars(select(OpsItem).where(OpsItem.kind == "task"))
    }
    added = 0
    for title, body in LAUNCH_CHECKLIST:
        if title not in existing:
            session.add(
                OpsItem(
                    kind="task",
                    title=title,
                    body=body,
                    status="new",
                    created_by_email="karen-ops",
                )
            )
            added += 1
    return added


def load_catalog(session: Session) -> dict[str, int]:
    """Load/refresh the full production catalog. Idempotent, insert-only
    for policies/channels (human edits are never overwritten)."""
    companies_added = 0
    for name, industry in PRODUCTION_COMPANIES:
        company = session.scalars(select(Company).where(Company.name == name)).first()
        if company is None:
            company = Company(name=name, industry=industry, size_class="enterprise")
            session.add(company)
            session.flush()
            companies_added += 1
        else:
            # Upgrade a previously user-created (unclassified) row to the
            # curated spec.
            company.industry = industry
            company.size_class = "enterprise"
        if name in COMPANY_INTEL and not company.intel:
            company.intel = COMPANY_INTEL[name]
        load_research_channels(session, company)
    policies_added = load_tier1_policies(session)
    members_added = load_ops_members(session)
    tasks_added = load_launch_checklist(session)
    session.flush()
    return {
        "companies_added": companies_added,
        "policies_added": policies_added,
        "ops_members_added": members_added,
        "checklist_tasks_added": tasks_added,
    }

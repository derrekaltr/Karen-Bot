"""Dev-only router: seed demo data and drive the mock-email simulator.

Lets the web app exercise the complete case lifecycle locally: seed a user
and companies, then call /dev/tick to make the worker deliver queued mail and
ingest the simulated company's replies.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from karenbot.channels.mock_email import MockEmailAdapter
from karenbot.db.session import get_session_factory
from karenbot.domain.models import Company, CompanyPolicy, SupportChannel, User
from karenbot.simulator.personas import PERSONAS
from karenbot.workflows.worker import Worker

DEMO_EMAIL = "dana@example.com"

SEED_COMPANIES: "list[dict[str, Any]]" = [
    {
        "name": "Acme Air",
        "industry": "airline",
        "size_class": "enterprise",
        "channel": "refunds@acme.example",
        "purpose": "baggage and refund claims",
        "policy_type": "baggage_delay_expenses",
        "policy_summary": "Acme Air reimburses reasonable documented expenses caused by delayed baggage, up to $500.",
        "rules": {
            "claim_type": "baggage_delay_expenses",
            "basis": "entitlement",
            "max_amount": 500,
            "requires_evidence": True,
        },
    },
    {
        "name": "Chipotle",
        "industry": "restaurant",
        "size_class": "enterprise",
        "channel": "support@chipotle.example",
        "purpose": "order and billing issues",
        "policy_type": "incorrect_charge",
        "policy_summary": "Chipotle refunds incorrect or duplicate charges on verified orders.",
        "rules": {
            "claim_type": "incorrect_charge",
            "basis": "entitlement",
            "max_amount": 200,
            "requires_evidence": True,
        },
    },
    {
        "name": "Delta Air Lines",
        "industry": "airline",
        "size_class": "enterprise",
        "channel": "refunds@delta.example",
        "purpose": "refunds and baggage claims",
        "policy_type": "flight_cancellation_refund",
        "policy_summary": "Refunds for cancelled flights to original form of payment; "
        "reasonable documented expenses for baggage delays.",
        "rules": {
            "claim_type": "flight_cancellation_refund",
            "basis": "entitlement",
            "max_amount": 2500,
            "requires_evidence": True,
        },
        "extra_policies": [
            {
                "policy_type": "baggage_delay_expenses",
                "policy_summary": "Reimburses reasonable documented baggage-delay expenses.",
                "rules": {
                    "claim_type": "baggage_delay_expenses",
                    "basis": "entitlement",
                    "max_amount": 800,
                    "requires_evidence": True,
                },
            }
        ],
    },
    {
        "name": "American Airlines",
        "industry": "airline",
        "size_class": "enterprise",
        "channel": "customer.relations@aa.example",
        "purpose": "refunds, credits, and customer relations",
        "policy_type": "flight_credit_reissue",
        "policy_summary": "Trip credits from unflown tickets can be reissued or "
        "extended; expired credits are reviewed case by case.",
        "rules": {
            "claim_type": "flight_credit_reissue",
            "basis": "goodwill",
            "max_amount": 3000,
            "requires_evidence": False,
        },
        "extra_policies": [
            {
                "policy_type": "flight_cancellation_refund",
                "policy_summary": "Cancelled flights are refundable to the original "
                "form of payment on request.",
                "rules": {
                    "claim_type": "flight_cancellation_refund",
                    "basis": "entitlement",
                    "max_amount": 2500,
                    "requires_evidence": True,
                },
            }
        ],
    },
    {
        "name": "Southwest Airlines",
        "industry": "airline",
        "size_class": "enterprise",
        "channel": "relations@southwest.example",
        "purpose": "delay compensation and refunds",
        "policy_type": "flight_delay_compensation",
        "policy_summary": "Per Southwest's DOT settlement (through April 2027), "
        "passengers delayed 3+ hours by a controllable cause receive a "
        "transferable voucher of at least $75 on request — never automatic.",
        "rules": {
            "claim_type": "flight_delay_compensation",
            "basis": "entitlement",
            "max_amount": 500,
            "requires_evidence": False,
        },
    },
    {
        "name": "JetBlue",
        "industry": "airline",
        "size_class": "enterprise",
        "channel": "care@jetblue.example",
        "purpose": "customer service plan claims",
        "policy_type": "flight_delay_compensation",
        "policy_summary": "JetBlue's published Customer Service Plan: flat 5,000 "
        "TrueBlue points for controllable delays over 3 hours (or cancellation "
        "under 4 hours notice), automatic within 24h; TrueBlue account must be "
        "attached before the disruption; $12 meal voucher.",
        "rules": {
            "claim_type": "flight_delay_compensation",
            "basis": "entitlement",
            "max_amount": 500,
            "requires_evidence": False,
        },
    },
    {
        "name": "Uber",
        "industry": "rideshare",
        "size_class": "enterprise",
        "channel": "support@uber.example",
        "purpose": "trip and billing issues",
        "policy_type": "incorrect_charge",
        "policy_summary": "Refunds incorrect, duplicate, or inflated trip charges.",
        "rules": {
            "claim_type": "incorrect_charge",
            "basis": "entitlement",
            "max_amount": 300,
            "requires_evidence": True,
        },
    },
    {
        "name": "American Express",
        "industry": "financial",
        "size_class": "enterprise",
        "channel": "disputes@amex.example",
        "purpose": "fee and billing disputes",
        "policy_type": "fee_dispute",
        "policy_summary": "Reviews annual fees and service charges; goodwill waivers "
        "available for members in good standing.",
        "rules": {
            "claim_type": "fee_dispute",
            "basis": "goodwill",
            "max_amount": 700,
            "requires_evidence": False,
        },
    },
    {
        "name": "McDonald's",
        "industry": "restaurant",
        "size_class": "enterprise",
        "channel": "care@mcdonalds.example",
        "purpose": "order and app issues",
        "policy_type": "incorrect_charge",
        "policy_summary": "Refunds incorrect app orders and duplicate charges.",
        "rules": {
            "claim_type": "incorrect_charge",
            "basis": "entitlement",
            "max_amount": 150,
            "requires_evidence": True,
        },
    },
    {
        "name": "Amazon",
        "industry": "ecommerce",
        "size_class": "enterprise",
        "channel": "cs@amazon.example",
        "purpose": "orders, returns, refunds",
        "policy_type": "missing_refund",
        "policy_summary": "Issues refunds for undelivered items and unprocessed returns.",
        "rules": {
            "claim_type": "missing_refund",
            "basis": "entitlement",
            "max_amount": 1000,
            "requires_evidence": True,
        },
    },
    {
        "name": "Rosa's Corner Bakery",
        "industry": "restaurant",
        "size_class": "small_business",  # moral code: assist mode only
        "channel": None,
    },
]

# Generosity intelligence per company (INTERNAL TARGETING ONLY — informs
# what Karen asks for and expects; never asserted in negotiation). USD
# equivalents; sources in docs/research/company-generosity.md.
COMPANY_INTEL: dict[str, dict] = {
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

# NOTE: all seed channels are .example placeholders for the mock adapter.
# Real company intelligence (verified addresses, sourced policies) is a
# human-verified data task before any real outreach — never invented.


class SeedOut(BaseModel):
    user_email: str
    companies: list[str]


class TickIn(BaseModel):
    persona: str | None = None  # switch the simulated company's behavior
    ticks: int = 1


class TickOut(BaseModel):
    work_done: int
    emails_sent_total: int
    persona: str


def _seed_tier1_policies(session) -> None:
    """Load Tier 1 compensation-policy research (data_compensation_policies).
    PRIMARY-confidence records seed verified; others unverified pending
    human review (eligibility ignores unverified policies)."""
    from karenbot.data_compensation_policies import TIER1_COMPANIES

    for name, spec in TIER1_COMPANIES.items():
        company = session.scalars(select(Company).where(Company.name == name)).first()
        if company is None:
            company = Company(
                name=name, industry=spec["industry"], size_class="enterprise"
            )
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


def _seed_demo_events(session) -> None:
    """Two clearly-labeled DEMO claim events so the /events page has content
    in a fresh sandbox. Real events only ever enter as research-agent drafts
    that a human publishes — never seeded."""
    from datetime import timedelta

    from karenbot.domain.models import ClaimEvent

    if session.scalars(select(ClaimEvent)).first() is not None:
        return
    today = datetime.now(UTC).date()
    acme = session.scalars(select(Company).where(Company.name == "Acme Air")).first()
    session.add(
        ClaimEvent(
            company_id=acme.id if acme else None,
            company_name="Acme Air",
            title="Demo: nationwide ground stop canceled 1,200 flights",
            summary=(
                "Demo data. A systems failure grounded Acme Air's fleet for six "
                "hours; flights were canceled through the evening."
            ),
            event_date=today - timedelta(days=1),
            region="US",
            entitlement=(
                "A cash refund to your original payment for any canceled flight "
                "you didn't take — a voucher is not a refund."
            ),
            eligibility="Anyone whose Acme Air flight was canceled that day.",
            how_to_claim="Request the refund via Acme Air's website; no form fee.",
            claim_deadline=None,
            category="flight_cancellation_refund",
            source_urls=["https://example.com/demo-ground-stop"],
            status="published",
            created_by="seed",
        )
    )
    att = session.scalars(select(Company).where(Company.name == "AT&T")).first()
    session.add(
        ClaimEvent(
            company_id=att.id if att else None,
            company_name="AT&T",
            title="Demo: regional fiber outage, 4 hours",
            summary=(
                "Demo data. A fiber cut knocked out home internet across several "
                "metro areas for about four hours."
            ),
            event_date=today - timedelta(days=2),
            region="Southeast US",
            entitlement="A full day's bill credit under the AT&T Guarantee.",
            eligibility="Fiber customers in the affected metros during the outage.",
            how_to_claim=(
                "AT&T emails affected customers a redemption link — click it "
                "within 30 days."
            ),
            claim_deadline=today + timedelta(days=28),
            category="outage_credit",
            source_urls=["https://example.com/demo-fiber-outage"],
            status="published",
            created_by="seed",
        )
    )


def _seed_research_channels(session, company, existing_addresses) -> None:
    """Load researched real-world channels as UNVERIFIED rows (policy engine
    refuses to send until a human verifies each in the admin console)."""
    from karenbot.data_support_channels import RESEARCH_CHANNELS

    for channel_type, address, purpose, is_escalation, source in RESEARCH_CHANNELS.get(
        company.name, []
    ):
        if address in existing_addresses:
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


def build_router(
    get_adapter: "Callable[[], MockEmailAdapter]", get_worker: "Callable[[], Worker]"
) -> APIRouter:
    """Takes getters (not instances) so the live adapter/worker can be
    swapped (tests, persona changes) without rebuilding the router."""
    router = APIRouter()

    @router.post("/seed", response_model=SeedOut)
    def seed() -> SeedOut:
        # Multiple pages call seed on mount; concurrent first-seeds can race
        # past the existence checks. The loser's IntegrityError just means
        # the winner already seeded — report success either way.
        try:
            return _do_seed()
        except IntegrityError:
            return SeedOut(
                user_email=DEMO_EMAIL, companies=[s["name"] for s in SEED_COMPANIES]
            )

    def _do_seed() -> SeedOut:
        factory = get_session_factory()
        with factory() as session:
            user = session.scalars(select(User).where(User.email == DEMO_EMAIL)).first()
            if user is None:
                session.add(User(email=DEMO_EMAIL, display_name="Dana Example"))
            names = []
            for spec in SEED_COMPANIES:
                names.append(spec["name"])
                company = session.scalars(
                    select(Company).where(Company.name == spec["name"])
                ).first()
                if company is None:
                    company = Company(
                        name=spec["name"],
                        industry=spec["industry"],
                        size_class=spec["size_class"],
                    )
                    session.add(company)
                    session.flush()
                else:
                    # Upgrade a previously user-created (unclassified) row to
                    # the curated spec — e.g. a company someone typed into
                    # "Other company" before it joined the catalog.
                    company.industry = spec["industry"]
                    company.size_class = spec["size_class"]
                existing_channels = {
                    c.address
                    for c in session.scalars(
                        select(SupportChannel).where(SupportChannel.company_id == company.id)
                    )
                }
                existing_policies = {
                    p.policy_type
                    for p in session.scalars(
                        select(CompanyPolicy).where(CompanyPolicy.company_id == company.id)
                    )
                }
                if spec["name"] in COMPANY_INTEL and not company.intel:
                    company.intel = COMPANY_INTEL[spec["name"]]
                _seed_research_channels(session, company, existing_channels)
                if spec.get("channel") and spec["channel"] in existing_channels:
                    continue
                if spec.get("channel") and spec["policy_type"] in existing_policies:
                    continue
                if spec.get("channel"):
                    session.add(
                        SupportChannel(
                            company_id=company.id,
                            channel="email",
                            address=spec["channel"],
                            purpose=spec["purpose"],
                            verified=True,
                            verification_source_url=f"https://{spec['name'].lower().replace(' ', '')}.example/contact",
                            verified_at=datetime.now(UTC),
                        )
                    )
                    session.add(
                        CompanyPolicy(
                            company_id=company.id,
                            policy_type=spec["policy_type"],
                            verified_at=datetime.now(UTC),
                            content={"summary": spec["policy_summary"]},
                            eligibility_rules=spec["rules"],
                        )
                    )
                    for extra in spec.get("extra_policies", []):
                        session.add(
                            CompanyPolicy(
                                company_id=company.id,
                                policy_type=extra["policy_type"],
                                verified_at=datetime.now(UTC),
                                content={"summary": extra["policy_summary"]},
                                eligibility_rules=extra["rules"],
                            )
                        )
            _seed_tier1_policies(session)
            _seed_demo_events(session)
            session.commit()
        return SeedOut(user_email=DEMO_EMAIL, companies=names)

    @router.post("/tick", response_model=TickOut)
    def tick(payload: TickIn) -> TickOut:
        adapter = get_adapter()
        worker = get_worker()
        persona_name = payload.persona or "lowball_then_accept"
        if payload.persona:
            adapter.responder = PERSONAS[payload.persona]
        elif adapter.responder is None:
            adapter.responder = PERSONAS[persona_name]
        work = 0
        for _ in range(max(1, min(payload.ticks, 10))):
            work += worker.tick()
        return TickOut(
            work_done=work,
            emails_sent_total=len(adapter.sent),
            persona=persona_name,
        )

    return router

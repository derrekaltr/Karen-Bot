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
                if company is not None:
                    continue
                company = Company(
                    name=spec["name"],
                    industry=spec["industry"],
                    size_class=spec["size_class"],
                )
                session.add(company)
                session.flush()
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

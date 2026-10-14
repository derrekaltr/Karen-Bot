import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated database per test: SQLite by default; set
    KARENBOT_TEST_DATABASE_URL to run the same suite against Postgres."""
    url = os.environ.get("KARENBOT_TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("KARENBOT_DATABASE_URL", url)
    monkeypatch.setenv("KARENBOT_MIN_HOURS_BETWEEN_OUTBOUND", "0")
    monkeypatch.setenv("KARENBOT_MAX_OUTBOUND_PER_CASE_PER_DAY", "10")

    from karenbot.config import get_settings

    get_settings.cache_clear()
    import karenbot.db.session as dbs

    dbs._engine = None
    dbs._session_factory = None

    from karenbot.db.base import Base
    from karenbot.domain import models  # noqa: F401

    engine = dbs.get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield dbs.get_session_factory()

    engine.dispose()
    get_settings.cache_clear()
    dbs._engine = None
    dbs._session_factory = None


@pytest.fixture
def seeded(db):
    """A user, company (verified channel + policy), and an authorized case
    in READY_TO_CONTACT with evidence attached."""
    from karenbot import services
    from karenbot.domain.enums import ActorType, CaseEvent
    from karenbot.domain.models import Company, CompanyPolicy, SupportChannel, User
    from karenbot.domain.state_machine import transition

    with db() as session:
        user = User(email="dana@example.com", display_name="Dana Example")
        company = Company(name="Acme Air", industry="airline")
        session.add_all([user, company])
        session.flush()
        channel = SupportChannel(
            company_id=company.id,
            channel="email",
            address="refunds@acme.example",
            purpose="refunds",
            verified=True,
            verified_at=datetime.now(UTC),
        )
        session.add(channel)
        session.add(
            CompanyPolicy(
                company_id=company.id,
                policy_type="baggage_delay_expenses",
                verified_at=datetime.now(UTC),
                content={"summary": "Reimburses documented baggage-delay expenses up to $500."},
                eligibility_rules={
                    "claim_type": "baggage_delay_expenses",
                    "basis": "entitlement",
                    "max_amount": 500,
                    "requires_evidence": True,
                },
            )
        )
        case = services.create_case(
            session,
            user=user,
            company=company,
            category="baggage_delay_expenses",
            description="Bag on AA 1234 delayed 3 days; spent $350 on essentials.",
            requested_amount=Decimal("350.00"),
        )
        evidence = services.add_evidence(
            session, case, evidence_type="receipt", summary="$350 receipts"
        )
        transition(session, case, CaseEvent.INTAKE_COMPLETE, actor_type=ActorType.AGENT)
        transition(session, case, CaseEvent.ELIGIBILITY_CONFIRMED, actor_type=ActorType.AGENT)
        services.grant_full_authorization(session, case)
        session.commit()
        ids = {
            "user_id": user.id,
            "company_id": company.id,
            "case_id": case.id,
            "channel_id": channel.id,
            "evidence_id": evidence.id,
        }
    return db, ids

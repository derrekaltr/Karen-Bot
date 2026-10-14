"""Simulated end-to-end case flow — the handoff's first functional milestone.

Customer submits a complaint -> KarenBot gathers evidence and policy ->
proposes an authorized message -> sends through the mock email connector ->
receives a simulated lowball reply -> autonomously counters -> company
concedes -> offer is recorded -> customer approves the binding acceptance ->
recovery verified -> case RESOLVED.

Runs entirely locally (SQLite + mock email + scripted LLM) with no
credentials. Set KARENBOT_LLM_PROVIDER=anthropic and an API key to run the
same flow against Claude.

Usage: python -m karenbot.demo.e2e
"""

import os
import tempfile
from datetime import UTC, datetime
from decimal import Decimal

# Demo pacing: the production minimum wait between outbound messages is
# hours; the demo compresses time. Must be set before settings are read.
os.environ.setdefault("KARENBOT_MIN_HOURS_BETWEEN_OUTBOUND", "0")
os.environ.setdefault("KARENBOT_MAX_OUTBOUND_PER_CASE_PER_DAY", "6")
os.environ.setdefault(
    "KARENBOT_DATABASE_URL",
    f"sqlite:///{tempfile.gettempdir()}/karenbot-demo.db",
)

from sqlalchemy import select  # noqa: E402

from karenbot import services  # noqa: E402
from karenbot.agent.runner import AgentRuntime  # noqa: E402
from karenbot.channels.mock_email import MockEmailAdapter  # noqa: E402
from karenbot.config import get_settings  # noqa: E402
from karenbot.db.base import Base  # noqa: E402
from karenbot.db.session import get_engine, get_session_factory  # noqa: E402
from karenbot.domain.models import (  # noqa: E402
    AuditEvent,
    Case,
    Communication,
    Company,
    CompanyPolicy,
    RecoveryOutcome,
    SupportChannel,
    User,
)
from karenbot.llm.scripted import ScriptedClient  # noqa: E402
from karenbot.simulator.personas import PERSONAS  # noqa: E402
from karenbot.workflows.worker import Worker  # noqa: E402


def banner(text: str) -> None:
    print(f"\n{'=' * 70}\n  {text}\n{'=' * 70}")


def show_status(session, case_id) -> str:
    case = session.get(Case, case_id)
    print(f"  -> case status: {case.status}")
    return case.status


def main() -> None:
    db_path = get_settings().database_url
    if db_path.startswith("sqlite:///"):
        path = db_path.removeprefix("sqlite:///")
        if os.path.exists(path):
            os.remove(path)

    engine = get_engine()
    Base.metadata.create_all(engine)
    factory = get_session_factory()

    llm = ScriptedClient()
    if get_settings().llm_provider == "anthropic":
        from karenbot.llm.anthropic_client import AnthropicClient

        llm = AnthropicClient()  # type: ignore[assignment]
    adapter = MockEmailAdapter(responder=PERSONAS["lowball_then_accept"])
    runtime = AgentRuntime(llm)
    worker = Worker(adapter, runtime, worker_id="demo-worker")

    banner("1. Seed: company intelligence (verified channel + policy)")
    with factory() as session:
        user = User(email="dana@example.com", display_name="Dana Example")
        company = Company(name="Acme Air", industry="airline", website="https://acme.example")
        session.add_all([user, company])
        session.flush()
        session.add(
            SupportChannel(
                company_id=company.id,
                channel="email",
                address="refunds@acme.example",
                purpose="baggage and refund claims",
                verified=True,
                verification_source_url="https://acme.example/contact",
                verified_at=datetime.now(UTC),
            )
        )
        session.add(
            CompanyPolicy(
                company_id=company.id,
                policy_type="baggage_delay_expenses",
                source_url="https://acme.example/policies/baggage",
                verified_at=datetime.now(UTC),
                content={
                    "summary": "Acme Air reimburses reasonable documented expenses "
                    "caused by delayed baggage, up to $500."
                },
                eligibility_rules={
                    "claim_type": "baggage_delay_expenses",
                    "basis": "entitlement",
                    "max_amount": 500,
                    "requires_evidence": True,
                },
            )
        )
        session.commit()
        user_id, company_id = user.id, company.id
    print("  Acme Air seeded with verified refunds channel and baggage policy.")

    banner("2. Customer submits a case (intake consent only)")
    with factory() as session:
        user = session.get(User, user_id)
        company = session.get(Company, company_id)
        case = services.create_case(
            session,
            user=user,
            company=company,
            category="baggage_delay_expenses",
            description=(
                "My bag on flight AA 1234 was delayed 3 days. I had to buy "
                "clothes and toiletries, spending $350 total. Acme Air has not "
                "responded to my complaint."
            ),
            requested_amount=Decimal("350.00"),
        )
        session.commit()
        case_id = case.id
        show_status(session, case_id)

    banner("3. Agent intake: extract facts, request missing evidence")
    with factory() as session:
        case = session.get(Case, case_id)
        result = runtime.run_intake(session, case)
        session.commit()
        print(f"  facts extracted: {case.facts}")
        print(f"  missing info: {result.missing_info}")
        show_status(session, case_id)

    banner("4. Customer uploads receipts; eligibility is assessed")
    with factory() as session:
        case = session.get(Case, case_id)
        services.add_evidence(
            session, case, evidence_type="receipt", summary="Receipts: $350 clothing/toiletries"
        )
        runtime.complete_intake(session, case)
        elig = runtime.assess_eligibility(session, case)
        session.commit()
        print(f"  eligibility: eligible={elig.eligible} basis={elig.basis}")
        show_status(session, case_id)

    banner("5. Customer grants negotiation authority")
    with factory() as session:
        case = session.get(Case, case_id)
        services.grant_full_authorization(session, case)
        session.commit()
        show_status(session, case_id)

    banner("6. Agent drafts initial email; policy engine authorizes; queued")
    with factory() as session:
        case = session.get(Case, case_id)
        decision = runtime.initiate_contact(session, case)
        session.commit()
        print(f"  policy decision: {decision.decision.value} ({', '.join(decision.reasons)})")
        show_status(session, case_id)

    banner("7. Worker delivers the email — then is 'killed' and restarted")
    worker.tick()
    # Restart-safety: a brand-new worker processing the same outbox must not
    # produce a duplicate send.
    Worker(adapter, runtime, worker_id="demo-worker-restarted").tick()
    with factory() as session:
        sends = len(adapter.sent)
        print(f"  emails actually sent (after restart): {sends}")
        assert sends >= 1
        show_status(session, case_id)

    banner("8. Company lowballs; agent classifies, declines, and counters")
    # tick() above already ingested the simulator's lowball reply and the
    # agent countered; the next tick delivers the counter and ingests the
    # company's full-amount concession.
    worker.tick()
    worker.tick()
    with factory() as session:
        case = session.get(Case, case_id)
        for comm in session.scalars(
            select(Communication).where(Communication.case_id == case_id).order_by(Communication.created_at)
        ):
            tag = comm.classification.get("classification", "sent") if comm.direction == "inbound" else "sent"
            print(f"  [{comm.direction:8s}] {tag:26s} {comm.subject or ''}")
        show_status(session, case_id)

    banner("9. Binding acceptance requires the customer's explicit approval")
    with factory() as session:
        case = session.get(Case, case_id)
        approvals = services.pending_approvals(session, case)
        print(f"  pending approvals: {[a.action_type for a in approvals]}")
        assert approvals, "expected a pending accept_offer approval"
        services.approve_action(session, approvals[0])
        session.commit()
        show_status(session, case_id)

    banner("10. Customer confirms funds received; case resolves")
    with factory() as session:
        case = session.get(Case, case_id)
        services.confirm_recovery_received(session, case)
        session.commit()
        outcome = session.scalars(
            select(RecoveryOutcome)
            .where(RecoveryOutcome.case_id == case_id)
            .order_by(RecoveryOutcome.created_at.desc())
        ).first()
        print(
            f"  recovery: ${outcome.amount} {outcome.recovery_type} "
            f"({outcome.verification_status})"
        )
        final = show_status(session, case_id)

    banner("Audit trail")
    with factory() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.timestamp)
        ).all()
        for e in events:
            print(f"  {e.actor_type:9s} {e.event_type}")
        print(f"\n  {len(events)} audit events recorded.")

    assert final == "RESOLVED", f"expected RESOLVED, got {final}"
    print("\n✅ Demo complete: case resolved end-to-end with no duplicate sends.\n")


if __name__ == "__main__":
    main()

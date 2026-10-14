"""Respect-the-refusal: when a company says "customers only," agent-sent
outreach stops permanently for that company and KarenBot switches to drafting
messages the customer sends personally. We never evade the preference."""

from sqlalchemy import select

from karenbot.agent.runner import AgentRuntime
from karenbot.channels.mock_email import MockEmailAdapter
from karenbot.domain.enums import PolicyDecisionType
from karenbot.domain.models import AuditEvent, Case, Communication, Company
from karenbot.llm.scripted import ScriptedClient
from karenbot.simulator.personas import PERSONAS
from karenbot.workflows.worker import Worker


def test_refusal_flips_company_flag_and_drafts_for_customer(seeded):
    db, ids = seeded
    adapter = MockEmailAdapter(responder=PERSONAS["customer_only"])
    runtime = AgentRuntime(ScriptedClient())
    worker = Worker(adapter, runtime, worker_id="refusal-test")

    with db() as session:
        case = session.get(Case, ids["case_id"])
        runtime.initiate_contact(session, case)
        session.commit()

    for _ in range(3):
        worker.tick()

    with db() as session:
        # Company is flagged and the refusal is audited.
        company = session.get(Company, ids["company_id"])
        assert company.refuses_third_party is True
        flags = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "channel.third_party_refusal_recorded"
            )
        ).all()
        assert flags

        # A first-person draft was produced for the customer (not sent).
        drafts = session.scalars(
            select(Communication).where(
                Communication.case_id == ids["case_id"],
                Communication.counterparty == "customer",
            )
        ).all()
        assert any((d.classification or {}).get("draft_for_customer") for d in drafts)
        draft = next(d for d in drafts if (d.classification or {}).get("draft_for_customer"))
        assert "KarenBot" not in draft.body  # customer's own voice

    # Only the single initial agent email ever went out.
    assert len(adapter.sent) == 1


def test_policy_denies_sends_after_refusal(seeded):
    from karenbot.agent.actions import SendMessage
    from karenbot.policy.context import build_case_context
    from karenbot.policy.engine import evaluate

    db, ids = seeded
    with db() as session:
        company = session.get(Company, ids["company_id"])
        company.refuses_third_party = True
        case = session.get(Case, ids["case_id"])
        ctx = build_case_context(session, case)
        action = SendMessage(
            case_id=case.id,
            purpose="follow_up",
            support_channel_id=ids["channel_id"],
            subject="s",
            body="another try",
            claim_type="baggage_delay_expenses",
        )
        decision = evaluate(action, ctx)
        assert decision.decision == PolicyDecisionType.DENY
        assert "company_refused_third_party_contact" in decision.reasons


def test_loa_is_captured_on_authorization(db):
    from decimal import Decimal

    from karenbot import services
    from karenbot.domain.enums import ActorType, CaseEvent
    from karenbot.domain.models import User
    from karenbot.domain.state_machine import transition

    with db() as session:
        user = User(email="loa@example.com", display_name="Loa Tester")
        company = Company(name="BigCo", industry="airline", size_class="enterprise")
        session.add_all([user, company])
        session.flush()
        case = services.create_case(
            session,
            user=user,
            company=company,
            category="refund",
            description="x",
            requested_amount=Decimal("100"),
        )
        transition(session, case, CaseEvent.INTAKE_COMPLETE, actor_type=ActorType.AGENT)
        transition(session, case, CaseEvent.ELIGIBILITY_CONFIRMED, actor_type=ActorType.AGENT)
        auth = services.grant_full_authorization(
            session,
            case,
            signed_name="Loa Tester",
            signature_ip="203.0.113.7",
            signature_user_agent="pytest",
        )
        assert auth.loa_text and "LETTER OF AUTHORIZATION" in auth.loa_text
        assert "BigCo" in auth.loa_text and str(case.id) in auth.loa_text
        assert auth.signed_name == "Loa Tester"
        assert auth.signature_ip == "203.0.113.7"

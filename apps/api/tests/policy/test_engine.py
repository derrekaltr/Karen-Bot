"""Pure policy-engine tests: no database, no I/O."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from karenbot.agent.actions import AcceptOffer, SendMessage
from karenbot.domain.enums import CaseStatus, PolicyDecisionType
from karenbot.policy.context import AuthorizationSnapshot, CaseContext
from karenbot.policy.engine import evaluate

CASE_ID = uuid.uuid4()
CHANNEL_ID = uuid.uuid4()
EVIDENCE_ID = uuid.uuid4()
NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def make_auth(**overrides) -> AuthorizationSnapshot:
    defaults = dict(
        active=True,
        authorized_actions=frozenset({"send_message", "accept_offer"}),
        prohibited_actions=frozenset(),
        authorized_claim_types=frozenset({"baggage_delay_expenses"}),
        max_requested_amount=Decimal("500"),
    )
    defaults.update(overrides)
    return AuthorizationSnapshot(**defaults)


def make_ctx(**overrides) -> CaseContext:
    defaults = dict(
        case_id=CASE_ID,
        case_status=CaseStatus.READY_TO_CONTACT.value,
        company_size_class="enterprise",
        company_targetable=True,
        company_refuses_third_party=False,
        authorization=make_auth(),
        verified_support_channel_ids=frozenset({CHANNEL_ID}),
        evidence_ids=frozenset({EVIDENCE_ID}),
        outbound_count_24h=0,
        outbound_count_total=0,
        follow_ups_sent=0,
        last_inbound_at=None,
        user_outbound_24h=0,
        global_outbound_1h=0,
        last_outbound_at=None,
        recent_outbound_fingerprints=frozenset(),
        pending_outbox_fingerprints=frozenset(),
        max_outbound_per_day=3,
        max_outbound_total=12,
        max_follow_ups=4,
        min_hours_between_outbound=20,
    )
    defaults.update(overrides)
    return CaseContext(**defaults)


def make_send(**overrides) -> SendMessage:
    defaults = dict(
        case_id=CASE_ID,
        purpose="initial_request",
        support_channel_id=CHANNEL_ID,
        subject="Reimbursement request",
        body="Please reimburse $350 of documented expenses.",
        claim_type="baggage_delay_expenses",
        requested_amount=Decimal("350"),
        evidence_ids=[EVIDENCE_ID],
    )
    defaults.update(overrides)
    return SendMessage(**defaults)


def test_valid_send_is_allowed():
    decision = evaluate(make_send(), make_ctx(), now=NOW)
    assert decision.decision == PolicyDecisionType.ALLOW


def test_no_authorization_denies():
    decision = evaluate(make_send(), make_ctx(authorization=None), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "no_active_authorization" in decision.reasons


def test_action_not_in_grant_denies():
    auth = make_auth(authorized_actions=frozenset({"request_customer_info"}))
    decision = evaluate(make_send(), make_ctx(authorization=auth), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "action_not_authorized:send_message" in decision.reasons


def test_customer_prohibited_action_denies():
    auth = make_auth(prohibited_actions=frozenset({"send_message"}))
    decision = evaluate(make_send(), make_ctx(authorization=auth), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY


def test_unverified_recipient_denies():
    decision = evaluate(
        make_send(support_channel_id=uuid.uuid4()), make_ctx(), now=NOW
    )
    assert decision.decision == PolicyDecisionType.DENY
    assert "recipient_not_verified_support_channel" in decision.reasons


def test_unauthorized_claim_type_denies():
    decision = evaluate(make_send(claim_type="medical_billing"), make_ctx(), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "claim_type_not_authorized:medical_billing" in decision.reasons


def test_amount_over_authorized_ceiling_denies():
    decision = evaluate(make_send(requested_amount=Decimal("9999")), make_ctx(), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "requested_amount_exceeds_authorized_limit" in decision.reasons


def test_unknown_evidence_id_denies():
    decision = evaluate(make_send(evidence_ids=[uuid.uuid4()]), make_ctx(), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "evidence_not_found_on_case" in decision.reasons


def test_daily_limit_denies():
    decision = evaluate(make_send(), make_ctx(outbound_count_24h=3), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "daily_outbound_limit_reached" in decision.reasons


def test_total_limit_denies():
    decision = evaluate(make_send(), make_ctx(outbound_count_total=12), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY


def test_minimum_wait_between_messages_denies():
    ctx = make_ctx(last_outbound_at=NOW - timedelta(hours=2))
    decision = evaluate(make_send(), ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "minimum_wait_between_messages_not_met" in decision.reasons


def test_replying_to_company_exempt_from_pacing():
    """Answering the company's latest message promptly is not harassment."""
    ctx = make_ctx(
        last_outbound_at=NOW - timedelta(hours=1),
        last_inbound_at=NOW - timedelta(minutes=10),  # they wrote after us
    )
    assert evaluate(make_send(), ctx, now=NOW).decision == PolicyDecisionType.ALLOW


def test_unprompted_resend_still_paced():
    ctx = make_ctx(
        last_outbound_at=NOW - timedelta(hours=1),
        last_inbound_at=NOW - timedelta(hours=5),  # we wrote last
    )
    decision = evaluate(make_send(), ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "minimum_wait_between_messages_not_met" in decision.reasons


def test_wait_elapsed_allows():
    ctx = make_ctx(last_outbound_at=NOW - timedelta(hours=21))
    decision = evaluate(make_send(), ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.ALLOW


def test_duplicate_content_denies():
    action = make_send()
    ctx = make_ctx(recent_outbound_fingerprints=frozenset({action.fingerprint()}))
    decision = evaluate(action, ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "duplicate_message_content" in decision.reasons


def test_queued_duplicate_denies():
    action = make_send()
    ctx = make_ctx(pending_outbox_fingerprints=frozenset({action.fingerprint()}))
    assert evaluate(action, ctx, now=NOW).decision == PolicyDecisionType.DENY


def test_max_follow_ups_denies():
    decision = evaluate(make_send(is_follow_up=True), make_ctx(follow_ups_sent=4), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "max_follow_ups_reached" in decision.reasons


def test_case_status_gates_contact():
    ctx = make_ctx(case_status=CaseStatus.AWAITING_AUTHORIZATION.value)
    decision = evaluate(make_send(), ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.DENY


def test_kill_switch_denies_everything():
    decision = evaluate(make_send(), make_ctx(kill_switch_active=True), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "kill_switch_active" in decision.reasons


def test_accept_offer_always_needs_approval():
    action = AcceptOffer(
        case_id=CASE_ID,
        purpose="accept",
        recovery_outcome_id=uuid.uuid4(),
        binding=True,
    )
    ctx = make_ctx(case_status=CaseStatus.OFFER_RECEIVED.value)
    decision = evaluate(action, ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.NEEDS_APPROVAL


def test_deny_wins_over_approval():
    action = AcceptOffer(
        case_id=CASE_ID,
        purpose="accept",
        recovery_outcome_id=uuid.uuid4(),
        binding=True,
    )
    auth = make_auth(authorized_actions=frozenset({"send_message"}))
    decision = evaluate(action, make_ctx(authorization=auth), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY


def test_user_daily_limit_across_cases_denies():
    decision = evaluate(make_send(), make_ctx(user_outbound_24h=10), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "user_daily_outbound_limit_reached" in decision.reasons


def test_global_hourly_circuit_breaker_denies():
    decision = evaluate(make_send(), make_ctx(global_outbound_1h=100), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "global_hourly_outbound_limit_reached" in decision.reasons


def test_small_business_is_never_contacted():
    """Moral code: mom-and-pop businesses are off-limits."""
    ctx = make_ctx(company_size_class="small_business", company_targetable=False)
    decision = evaluate(make_send(), ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "company_not_targetable:small_business" in decision.reasons


def test_unclassified_company_is_not_contacted():
    """Safe default: unreviewed companies are left alone."""
    ctx = make_ctx(company_size_class="unclassified", company_targetable=False)
    decision = evaluate(make_send(), ctx, now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "company_not_targetable:unclassified" in decision.reasons


def test_case_id_mismatch_denies():
    decision = evaluate(make_send(case_id=uuid.uuid4()), make_ctx(), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "action_case_mismatch" in decision.reasons


def test_escalation_requires_prior_regular_contact():
    from karenbot.agent.actions import RecommendEscalation

    action = RecommendEscalation(
        case_id=CASE_ID,
        purpose="escalate",
        target_support_channel_id=CHANNEL_ID,
        reason="no response",
    )
    auth = make_auth(authorized_actions=frozenset({"recommend_escalation"}))
    decision = evaluate(action, make_ctx(authorization=auth, outbound_count_total=0), now=NOW)
    assert decision.decision == PolicyDecisionType.DENY
    assert "escalation_before_first_contact" in decision.reasons

    decision = evaluate(action, make_ctx(authorization=auth, outbound_count_total=2), now=NOW)
    assert decision.decision == PolicyDecisionType.ALLOW

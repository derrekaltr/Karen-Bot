"""The deterministic policy engine.

`evaluate()` is pure: no I/O, no clock reads (time enters via the context),
no randomness. Every proposed agent action passes through here before
anything is executed. The engine can only ALLOW, DENY, or require approval —
it never modifies the action.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from karenbot.agent.actions import (
    SENSITIVE_ACTION_TYPES,
    AcceptOffer,
    CloseCase,
    DraftForCustomer,
    ProposedAction,
    RecommendEscalation,
    RecordOffer,
    RequestCustomerInfo,
    ScheduleFollowUp,
    SendMessage,
)
from karenbot.domain.enums import CONTACTABLE_STATES, PolicyDecisionType
from karenbot.policy.context import CaseContext


@dataclass(frozen=True)
class PolicyDecision:
    decision: PolicyDecisionType
    reasons: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision == PolicyDecisionType.ALLOW


def evaluate(
    action: ProposedAction, ctx: CaseContext, *, now: datetime | None = None
) -> PolicyDecision:
    now = now or datetime.now(UTC)
    deny: list[str] = []
    approval: list[str] = []

    # --- Checks that apply to every action -------------------------------
    if ctx.kill_switch_active:
        deny.append("kill_switch_active")

    if action.case_id != ctx.case_id:
        deny.append("action_case_mismatch")

    auth = ctx.authorization
    if auth is None or not auth.active:
        deny.append("no_active_authorization")
    else:
        action_type = action.action
        if action_type in auth.prohibited_actions:
            deny.append(f"action_prohibited_by_customer:{action_type}")
        if action_type not in auth.authorized_actions:
            deny.append(f"action_not_authorized:{action_type}")

    if action.action in SENSITIVE_ACTION_TYPES or action.risk_level == "high":
        approval.append(f"sensitive_action_requires_customer_approval:{action.action}")

    # Moral code: company-facing pressure is only ever applied to large
    # enterprises. Small businesses and unclassified companies are off-limits
    # for any outward action, full stop.
    if isinstance(action, (SendMessage, RecommendEscalation)) and not ctx.company_targetable:
        deny.append(f"company_not_targetable:{ctx.company_size_class}")

    # Respect-the-refusal: once a company says it only deals with customers
    # directly, agent-sent contact stops. We assist the customer instead
    # (draft_for_customer) — we never evade the preference.
    if isinstance(action, (SendMessage, RecommendEscalation)) and ctx.company_refuses_third_party:
        deny.append("company_refused_third_party_contact")

    # --- Action-specific checks ------------------------------------------
    if isinstance(action, SendMessage):
        _check_send_message(action, ctx, now, deny)
    elif isinstance(action, AcceptOffer):
        if action.binding:
            approval.append("binding_settlement_requires_customer_approval")
    elif isinstance(
        action,
        (RecordOffer, RequestCustomerInfo, ScheduleFollowUp, CloseCase, DraftForCustomer),
    ):
        pass  # internal/customer-facing actions: authorization check above suffices
    elif isinstance(action, RecommendEscalation):
        if action.target_support_channel_id not in ctx.verified_support_channel_ids:
            deny.append("escalation_target_not_verified")

    if deny:
        return PolicyDecision(PolicyDecisionType.DENY, deny)
    if approval:
        return PolicyDecision(PolicyDecisionType.NEEDS_APPROVAL, approval)
    return PolicyDecision(PolicyDecisionType.ALLOW, ["all_checks_passed"])


def _check_send_message(
    action: SendMessage, ctx: CaseContext, now: datetime, deny: list[str]
) -> None:
    if ctx.case_status not in CONTACTABLE_STATES:
        deny.append(f"case_status_not_contactable:{ctx.case_status}")

    # Recipient must be a verified, active support channel for this company.
    if action.support_channel_id not in ctx.verified_support_channel_ids:
        deny.append("recipient_not_verified_support_channel")

    # Claim type must be within the customer's authorization.
    auth = ctx.authorization
    if auth is not None and action.claim_type not in auth.authorized_claim_types:
        deny.append(f"claim_type_not_authorized:{action.claim_type}")

    # Requested amount must not exceed the authorized ceiling.
    if (
        auth is not None
        and auth.max_requested_amount is not None
        and action.requested_amount is not None
        and action.requested_amount > auth.max_requested_amount
    ):
        deny.append("requested_amount_exceeds_authorized_limit")

    # Evidence references must belong to this case (no fabricated evidence ids).
    unknown = set(action.evidence_ids) - set(ctx.evidence_ids)
    if unknown:
        deny.append("evidence_not_found_on_case")

    # Frequency limits.
    if ctx.outbound_count_24h >= ctx.max_outbound_per_day:
        deny.append("daily_outbound_limit_reached")
    if ctx.outbound_count_total >= ctx.max_outbound_total:
        deny.append("total_outbound_limit_reached")
    if action.is_follow_up and ctx.follow_ups_sent >= ctx.max_follow_ups:
        deny.append("max_follow_ups_reached")
    if ctx.last_outbound_at is not None:
        min_gap = timedelta(hours=ctx.min_hours_between_outbound)
        if now - ctx.last_outbound_at < min_gap:
            deny.append("minimum_wait_between_messages_not_met")

    # Duplicate detection: identical content already sent or queued.
    fp = action.fingerprint()
    if fp in ctx.recent_outbound_fingerprints or fp in ctx.pending_outbox_fingerprints:
        deny.append("duplicate_message_content")

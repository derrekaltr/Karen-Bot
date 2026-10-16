"""Case category catalog: industry-specific claim types with labels.

Grounded in complaint-volume research (docs/research/customer-request-
taxonomy.md): DOT Air Travel Consumer Reports, CFPB complaint database,
FTC Sentinel, FCC categories, plus industry surveys. Lists are ordered by
real-world frequency where data exists.

Categories serve three roles: scoping the customer's authorization
(claim-type allowlist), selecting eligibility rules, and labeling the UI.
The catalog is intentionally data, not an enum — any string is a legal
category (customers describe unpredicted situations via "Something
else…"); the catalog is what we *suggest*. Existing keys are kept stable
across taxonomy updates because cases, policies, and authorizations
reference them.

Excluded by policy (regulated; see docs/legal-risk.md): credit
reporting/repair, debt collection/settlement, loan servicing, insurance
claims, medical billing, scam-loss "recovery".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str


# Cross-industry request verbs — always available, any company.
GENERAL: list[Category] = [
    Category("refund_request", "Get my money back"),
    Category("fee_waiver", "Waive or reverse a fee"),
    Category("billing_error_correction", "Fix a billing error or double charge"),
    Category("cancel_no_penalty", "Cancel without penalty"),
    Category("price_adjustment", "Lower my price or honor a better rate"),
    Category("replace_or_redo", "Replace, reship, or redo"),
    Category("goodwill_credit", "Goodwill credit for a bad experience"),
    Category("restore_points_credit", "Restore points, miles, or credits"),
    Category("account_reinstate", "Reinstate or unlock my account"),
]

BY_INDUSTRY: dict[str, list[Category]] = {
    # Ordered by DOT complaint volume: refunds > flight problems > baggage.
    "airline": [
        Category("flight_cancellation_refund", "Flight cancelled or changed — get my refund"),
        Category("flight_delay_compensation", "Delay or cancellation — cover my expenses"),
        Category("baggage_delay_expenses", "Lost, delayed, or damaged bag"),
        Category("schedule_change_refund", "Airline changed my schedule — rebook or refund"),
        Category("ancillary_fee_refund", "Refund a seat, bag, or Wi-Fi fee I didn't get"),
        Category("missed_flight_recovery", "Missed my flight — recover value / credits"),
        Category("flight_credit_reissue", "Reissue or extend an expired travel credit"),
        Category("involuntary_downgrade", "Bumped to a worse seat or cabin — refund the difference"),
        Category("denied_boarding_compensation", "Bumped or denied boarding — compensation"),
        Category("booking_error_fix", "Booking, name, or fare error — fix it without a fee"),
        Category("miles_points_restore", "Restore lost miles or points"),
    ],
    # Hidden/resort fees are the #1 hotel complaint (AHLA, Consumer Reports).
    "hotel": [
        Category("resort_fee_dispute", "Resort or amenity fee — remove or refund"),
        Category("incorrect_charge", "Wrong or extra charge on my bill"),
        Category("room_quality_compensation", "Room wasn't as described — partial refund or points"),
        Category("noise_disturbance", "Noise or disturbance — compensation"),
        Category("cancellation_fee_dispute", "Cancellation or no-show fee dispute"),
        Category("overbooked_walked", "Hotel overbooked or walked me — compensation"),
        Category("loyalty_points_missing", "Missing loyalty points or elite benefit"),
        Category("third_party_booking_issue", "Booked via a travel site — reservation not honored"),
        Category("deposit_hold_release", "Release a deposit or hold on my card"),
    ],
    # Surge/fare disputes dominate (65% cite surge; 29% unfair cancel fees).
    "rideshare": [
        Category("incorrect_charge", "Charged more than the quoted fare (surge, route, tolls)"),
        Category("cancellation_fee_dispute", "Unfair cancellation or no-show fee"),
        Category("driver_cancel_noshow", "Driver cancelled or never showed — credit or refund"),
        Category("cleaning_damage_fee", "Cleaning or damage fee I disagree with"),
        Category("promo_credit_missing", "Missing promo or ride credit"),
        Category("unsafe_rude_driver", "Unsafe or bad trip — refund the ride"),
        Category("membership_cancel_refund", "Cancel my membership and refund the renewal"),
    ],
    # Missing/wrong items 22% of complaints; refunded-as-credit is a
    # distinct ask worth its own entry.
    "delivery_apps": [
        Category("missing_wrong_items", "Missing or wrong items — refund"),
        Category("late_order_credit", "Order was very late — credit or refund"),
        Category("cold_or_spoiled_food", "Food arrived cold or spoiled"),
        Category("marked_delivered_not_received", "Marked delivered but never arrived"),
        Category("credit_to_cash_refund", "Refunded as app credit — I want my money back"),
        Category("fee_markup_dispute", "Delivery fee, service fee, or price markup dispute"),
        Category("membership_cancel_refund", "Cancel my membership and refund the renewal"),
        Category("account_reinstate", "Account flagged or restricted — reinstate"),
    ],
    "restaurant": [
        Category("wrong_missing_dish", "Wrong or missing dish"),
        Category("incorrect_charge", "Billing error, double charge, or tip error"),
        Category("food_quality_issue", "Food was cold or poor quality — comp or refund"),
        Category("long_wait_service", "Long wait or bad service — comp the meal"),
        Category("reservation_fee_dispute", "Reservation deposit or no-show fee dispute"),
        Category("gift_card_loyalty_issue", "Gift card or loyalty balance problem"),
    ],
    # Undelivered goods are the #2 FTC fraud category.
    "ecommerce": [
        Category("undelivered_item", "Order never arrived — refund or reship"),
        Category("damaged_defective_item", "Item damaged or defective — replace or refund"),
        Category("wrong_missing_item", "Wrong or missing item in my order"),
        Category("missing_refund", "I returned it — refund hasn't come"),
        Category("failed_return", "Return denied or restocking fee — waive it"),
        Category("price_adjustment", "Price dropped after I bought — price adjustment"),
        Category("warranty_claim", "Warranty claim"),
        Category("shipping_fee_refund", "Late delivery — refund shipping"),
        Category("unauthorized_duplicate_order", "Unauthorized or duplicate order — refund"),
        Category("promo_not_applied", "Discount or promo code didn't apply"),
    ],
    # Narrow usable set once regulated work (credit reporting, debt) is
    # excluded — 85% + 7% of CFPB volume is out of scope by design.
    "financial": [
        Category("dispute_card_charge", "Dispute a charge on my card statement"),
        Category("fraud_reimbursement", "Reimburse fraud or an unauthorized charge"),
        Category("overdraft_bank_fee_waiver", "Waive or refund an overdraft or bank fee"),
        Category("fee_dispute", "Waive a late fee, interest, or annual fee"),
        Category("rewards_restoration", "Restore missing rewards, points, or a sign-up bonus"),
        Category("frozen_account_release", "Unfreeze my account or release held funds"),
        Category("payment_transfer_error", "Fix a failed or wrong payment or transfer"),
    ],
    # Billing errors lead; 70% who haggle get concessions.
    "telecom": [
        Category("incorrect_charge", "Billing error or surprise charge — credit it back"),
        Category("bill_negotiation", "Price went up or promo ended — lower my rate"),
        Category("outage_credit", "Outage or slow service — credit for downtime"),
        Category("equipment_fee_dispute", "Equipment or rental fee dispute"),
        Category("cancel_no_etf", "Cancel without early-termination fee"),
        Category("unauthorized_charge_removal", "Remove an unauthorized third-party charge"),
        Category("missed_appointment_credit", "Missed technician appointment — credit"),
        Category("promo_trade_in_credit_missing", "Missing promo or trade-in credit"),
    ],
    # B2B SaaS/cloud: SLA breaches are contractual, objectively measurable,
    # and chronically under-claimed (docs/research/compensation-likelihood.md).
    "saas": [
        Category("sla_service_credit", "SLA breach — claim service credits"),
        Category("outage_credit", "Outage or degraded service — credit"),
        Category("incorrect_charge", "Billing error or double charge"),
        Category("refund_unwanted_renewal", "Refund a renewal I didn't want"),
        Category("prorated_refund", "Refund unused time on an annual plan"),
    ],
    "car_rental": [
        Category("incorrect_charge", "Incorrect or surprise charge"),
        Category("deposit_hold_release", "Release my deposit or hold"),
        Category("reservation_failure", "Reservation not honored / no vehicle"),
        Category("prepaid_booking_refund", "Refund a prepaid booking issue"),
        Category("damage_claim_dispute", "Dispute a damage claim or fee"),
    ],
    "subscription": [
        Category("refund_unwanted_renewal", "Refund a renewal I didn't want"),
        Category("subscription_cancellation", "Cancel a subscription (even a hard-to-cancel one)"),
        Category("free_trial_charge", "Charged after a free trial or without consent"),
        Category("charged_after_cancel", "Charged after cancelling, or billed twice"),
        Category("price_hike_honor_rate", "Price increased — honor my old rate"),
        Category("recurring_charge_refund", "Refund recurring charges"),
        Category("prorated_refund", "Refund unused time on an annual plan"),
        Category("bill_negotiation", "Negotiate this bill down"),
    ],
}

# Industries a user can pick for an unknown company.
KNOWN_INDUSTRIES: list[str] = [*BY_INDUSTRY.keys(), "other"]


def options_for_industry(industry: str) -> list[Category]:
    specific = BY_INDUSTRY.get(industry, [])
    seen = {c.key for c in specific}
    return specific + [c for c in GENERAL if c.key not in seen]


def label_for(key: str) -> str:
    for group in [*BY_INDUSTRY.values(), GENERAL]:
        for category in group:
            if category.key == key:
                return category.label
    return key.replace("_", " ").capitalize()

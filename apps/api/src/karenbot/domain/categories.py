"""Case category catalog: industry-specific claim types with labels.

Categories serve three roles: scoping the customer's authorization
(claim-type allowlist), selecting eligibility rules, and labeling the UI.
The catalog is intentionally data, not an enum — any string is a legal
category (customers can describe situations we didn't predict via custom
categories); the catalog is what we *suggest* per industry.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str


GENERAL: list[Category] = [
    Category("refund_request", "Refund request"),
    Category("incorrect_charge", "Incorrect charge"),
    Category("service_failure", "Service failure"),
    Category("subscription_cancellation", "Cancel a subscription"),
    Category("bill_negotiation", "Negotiate a bill"),
]

BY_INDUSTRY: dict[str, list[Category]] = {
    "airline": [
        Category("missed_flight_recovery", "Missed my flight — recover value / credits"),
        Category("flight_cancellation_refund", "Cancelled flight refund"),
        Category("flight_delay_compensation", "Long delay — compensation / expenses"),
        Category("flight_credit_reissue", "Unused flight credits / expired vouchers"),
        Category("baggage_delay_expenses", "Delayed or lost baggage expenses"),
        Category("schedule_change_refund", "Schedule change wrecked my trip"),
        Category("involuntary_downgrade", "Involuntary downgrade compensation"),
        Category("missed_connection_expenses", "Missed connection expenses"),
        Category("goodwill_compensation", "Terrible experience — goodwill compensation"),
    ],
    "hotel": [
        Category("incorrect_charge", "Incorrect charge"),
        Category("failed_reservation", "Failed or walked reservation"),
        Category("service_failure_refund", "Service failure refund"),
    ],
    "rideshare": [
        Category("incorrect_charge", "Incorrect or inflated fare"),
        Category("refund_request", "Refund for a bad or unsafe trip"),
    ],
    "restaurant": [
        Category("incorrect_charge", "Incorrect charge"),
        Category("order_failure_refund", "Wrong or missing order refund"),
    ],
    "ecommerce": [
        Category("missing_refund", "Refund never arrived"),
        Category("undelivered_item", "Item never delivered"),
        Category("failed_return", "Return not processed"),
        Category("incorrect_charge", "Incorrect charge"),
    ],
    "financial": [
        Category("fee_dispute", "Annual fee / service fee dispute"),
        Category("interest_fee_waiver", "Interest or late-fee waiver"),
        Category("incorrect_charge", "Incorrect charge"),
    ],
    "telecom": [
        Category("bill_negotiation", "Negotiate my bill down"),
        Category("outage_credit", "Outage credit"),
        Category("incorrect_charge", "Incorrect charge"),
    ],
    "subscription": [
        Category("subscription_cancellation", "Cancel a subscription"),
        Category("recurring_charge_refund", "Refund recurring charges"),
        Category("bill_negotiation", "Negotiate a bill"),
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

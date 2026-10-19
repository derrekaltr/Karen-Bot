"""Tier 1 compensation-policy records (docs/research/policy-database-tier1.md).

Loaded by the dev seeder. Records with confidence PUBLISHED_PRIMARY (read on
the company's own page, 2026-10-19) seed as verified; SECONDARY/excerpt
records seed with verified_at=None, which the eligibility engine treats as
non-matching (goodwill fallback) until a human verifies them.
"""

# company -> {industry, size_class, policies: [...]}
TIER1_COMPANIES: dict[str, dict] = {
    "Amazon Web Services": {
        "industry": "saas",
        "policies": [{
            "policy_type": "sla_service_credit",
            "verified": True,
            "source_url": "https://aws.amazon.com/compute/sla/",
            "summary": "Per-service SLAs (EC2 99.99% region / 99.5% instance; S3, RDS, "
            "Lambda, CloudFront similar) with 10%/25-30%/100% credit ladders. Claim: "
            "Support Center case titled 'SLA Credit Request' with logs and resource "
            "IDs, by the end of the second billing cycle after the incident.",
            "rules": {"claim_type": "sla_service_credit", "basis": "entitlement",
                      "requires_evidence": True},
        }],
    },
    "Google Cloud": {
        "industry": "saas",
        "policies": [{
            "policy_type": "sla_service_credit",
            "verified": False,  # fetch truncated; excerpts only — human verify
            "source_url": "https://cloud.google.com/compute/sla",
            "summary": "Per-service SLAs (Compute 99.99% multi-zone, GKE regional "
            "99.95%, Storage/BigQuery capped at 50% credit). Claim windows: Compute "
            "60 days, others 30 days, via support case with log files.",
            "rules": {"claim_type": "sla_service_credit", "basis": "entitlement",
                      "requires_evidence": True},
        }],
    },
    "Microsoft Azure": {
        "industry": "saas",
        "policies": [{
            "policy_type": "sla_service_credit",
            "verified": False,  # ladders from 21Vianet mirrors; DOCX unread
            "source_url": "https://www.microsoft.com/licensing/docs/view/Service-Level-Agreements-SLA-for-Online-Services",
            "summary": "VM/AKS/Storage/SQL SLAs with 10%/25%/100% ladders. Claim: "
            "portal support request (Billing > Refund Request, 'SLA Credit Request') "
            "within two months of the end of the billing month; CSP via partner.",
            "rules": {"claim_type": "sla_service_credit", "basis": "entitlement",
                      "requires_evidence": True},
        }],
    },
    "Atlassian": {
        "industry": "saas",
        "policies": [{
            "policy_type": "sla_service_credit",
            "verified": True,
            "source_url": "https://www.atlassian.com/legal/sla",
            "summary": "Premium 99.9% (10/25/50%) and Enterprise 99.95% (5/10/25/50%) "
            "uptime SLAs. Claim: support ticket within 15 days of the end of the "
            "month; account fully paid; cap 100% of the product's invoice.",
            "rules": {"claim_type": "sla_service_credit", "basis": "entitlement",
                      "requires_evidence": True},
        }],
    },
    "Cloudflare": {
        "industry": "saas",
        "policies": [{
            "policy_type": "sla_service_credit",
            "verified": True,
            "source_url": "https://www.cloudflare.com/enterprise_support_sla/",
            "summary": "Enterprise 100% uptime SLA: 10x credit (Standard Success) or "
            "25x (Premium). Notify within 5 business days, submit by end of the "
            "following billing month, with traceroutes and affected URLs; annual cap "
            "6 months of fees. Business plan: pro-rata credit, cap 1 month/12mo.",
            "rules": {"claim_type": "sla_service_credit", "basis": "entitlement",
                      "requires_evidence": True},
        }],
    },
    "AT&T": {
        "industry": "telecom",
        "policies": [{
            "policy_type": "outage_credit",
            "verified": True,  # business/SMB pages read; consumer page 403
            "source_url": "https://www.business.att.com/about/business-guarantee.html",
            "summary": "AT&T Guarantee: fiber outage 20+ min or wireless 60+ min "
            "(8+ towers) earns a full-day bill credit; AT&T notifies by email/text "
            "and the customer must redeem via the link within 30 days. Excludes "
            "weather, third-party causes, home power outages.",
            "rules": {"claim_type": "outage_credit", "basis": "entitlement",
                      "requires_evidence": False},
        }],
    },
    "Comcast / Xfinity": {
        "industry": "telecom",
        "policies": [{
            "policy_type": "outage_credit",
            "verified": True,  # flow is primary; amounts unpublished
            "source_url": "https://www.xfinity.com/support/articles/check-service-outage",
            "summary": "Outage credits via Support > Outage map and credit > Check "
            "credit eligibility (enter outage dates; auto-applies if eligible, "
            "subject to an unpublished max). Separate 30-Day Money-Back Guarantee "
            "refunds new/changed services in full. NOTE: the famous $20 missed-"
            "appointment credit is a dead 2015 program — never cite it.",
            "rules": {"claim_type": "outage_credit", "basis": "entitlement",
                      "requires_evidence": False},
        }],
    },
    "Marriott": {
        "industry": "hotel",
        "policies": [{
            "policy_type": "overbooked_walked",
            "verified": True,
            "source_url": "https://www.marriott.com/loyalty/member-benefits/guarantee.mi",
            "summary": "Ultimate Reservation Guarantee: walked elite guests get the "
            "night nearby paid plus full-service brands $200 + 90,000 points; select "
            "brands $100 (+90k Platinum+); midscale $50 (+45k Platinum+); Ritz/St. "
            "Regis $200 + 140k (Titanium/Ambassador only). Claim at the front desk; "
            "escalate to Bonvoy Member Support.",
            "rules": {"claim_type": "overbooked_walked", "basis": "entitlement",
                      "max_amount": 1500, "requires_evidence": False},
        }],
    },
    "Delta Air Lines": {
        "industry": "airline",
        "policies": [{
            "policy_type": "flight_delay_compensation",
            "verified": True,
            "source_url": "https://www.delta.com/us/en/legal/customer-commitment",
            "summary": "Customer Commitment (eff. 2024-10-24): meals at 3h+ "
            "controllable delay; complimentary hotel + ground transport (or "
            "reimbursement of reasonable costs) for controllable overnight "
            "disruptions; reimbursement form for US/Canada residents. Cash/credit "
            "beyond this is discretionary, not an entitlement.",
            "rules": {"claim_type": "flight_delay_compensation", "basis": "entitlement",
                      "max_amount": 600, "requires_evidence": True},
        }],
    },
}

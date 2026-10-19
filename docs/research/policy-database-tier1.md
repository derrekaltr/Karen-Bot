# Tier 1 Compensation-Policy Database (research, 2026-10-19)

> Structured records for AWS, Google Cloud, Azure, Atlassian, Cloudflare,
> AT&T, Comcast/Xfinity, Marriott, JetBlue, Southwest, Delta. Confidence:
> PUBLISHED_PRIMARY (read on company's own page) / SECONDARY / UNVERIFIED.
> Loaded into seeds via `data_compensation_policies.py` (PRIMARY records
> seeded verified; SECONDARY/UNVERIFIED seeded unverified pending human
> review). Full per-record YAML follows the agent transcript; the
> operationally critical facts and corrections:

## Corrections to prior assumptions
1. Google Compute Engine SLA claim window is **60 days** (GKE/Storage/
   BigQuery are 30) — per-service windows, store per policy.
2. Azure claims: **two months after the end of the billing month** (the
   "end of following month" rule is M365, not Azure).
3. Cloudflare Enterprise: **10x credit on Standard** Success Offering,
   **25x only on Premium** (plans FAQ; SLA §10 needs human read).
4. Xfinity's famous $20 missed-appointment credit is **dead** (2015
   program; current pages omit it; staff post denies it). Do not use.
5. AT&T wireless threshold: 8 towers (current pages) vs 10 (2025 launch
   coverage) — likely lowered in the 2026 expansion; use 8, verify.

## Key records (abridged; claim mechanics)

### SaaS SLA credits (all: customer must file; credits to future bills)
- **AWS** (PRIMARY, per-service pages): EC2 region-level 99.99%/instance
  99.5%; S3 99.9%/99.0% by class; RDS Multi-AZ 99.95%; Lambda 99.95%;
  CloudFront 99.9%. Ladders ~10%/25-30%/100%. Claim: Support Center case,
  subject "SLA Credit Request", **by end of second billing cycle after
  incident**; logs + resource IDs required; $1 minimum credit.
- **Google Cloud** (excerpt-PRIMARY, re-verify): Compute 99.99% multi-zone
  /99.9% single (10/25/100%); GKE regional 99.95% (10/25/50%); Storage +
  BigQuery ladders cap **50%**. Claim via support; **Compute 60 days,
  others 30 days**; log files required.
- **Azure** (SECONDARY via 21Vianet mirrors; authoritative DOCX unread):
  VMs AZ 99.99%/set 99.95%/single 99.9-95% (10/25/100%); AKS uptime-SLA
  add-on; Storage per-redundancy; SQL per-tier to 99.995%. Claim: portal
  support request, Billing → Refund Request, "SLA Credit Request", within
  **two months of billing-month end**; CSP customers via partner.
- **Atlassian** (PRIMARY, eff. 2026-04-30): Premium 99.9% (10/25/50%),
  Enterprise 99.95% (5/10/25/50%). Claim: support ticket **within 15 days
  of month end**; account fully paid; cap 100% of invoice for product.
- **Cloudflare** (PRIMARY + FAQ): Enterprise 100% uptime; 10x (Standard) /
  25x (Premium) credit multiplier; notify **within 5 business days**,
  submit by end of following billing month; traceroutes + URLs required;
  annual cap 6 months of fees. Business plan: pro-rata credit, cap 1 month
  /12mo.

### Telecom
- **AT&T Guarantee** (PRIMARY business pages; consumer 403): fiber outage
  20+ min or wireless 60+ min (8+ towers) → full-day credit; notification
  automatic but customer must **redeem via emailed link within 30 days**;
  excludes weather/third-party/power-at-home. Business Internet SLA:
  99.9% availability/40ms/0.1% loss → 1 day credit per breach, needs
  Verifiable Trouble Ticket, request within 30 days.
- **Xfinity** (PRIMARY flow, amounts unpublished): outage credit via
  Support → Outage map and credit → Check eligibility (enter outage
  dates; auto-applies if eligible, under an unpublished max). 30-Day
  Money-Back Guarantee on new/changed services (full refund incl. fees);
  14-day Mobile guarantee.

### Hotel
- **Marriott URG** (PRIMARY): walked guests — full-service brands $200 +
  90k points (all elites); select brands $100 (+90k Plat+); midscale $50
  (+45k Plat+); Ritz/St. Regis $200 + 140k (Titanium/Ambassador only).
  Claim at the desk; escalate to Bonvoy Member Support. Welcome-gift
  guarantee $25–100 (amounts per brand unverified).

### Airlines
- **JetBlue** (PRIMARY ×3 pages): 5,000 TrueBlue points flat, automatic
  within 24h, controllable delay >3h or cancel <4h notice; TrueBlue
  attached beforehand; Canada/EU excluded. $12 meal voucher; hotel +
  transport or reimbursement (claims within 10 days, receipts). Bag fee
  auto-refund at 12h dom/15h intl. DB to $2,150.
- **Southwest** (Help Center PRIMARY; CSP PDF unread): meals/hotel/ground
  on request for controllable 3h+; reimbursement claims within 1 year via
  help-center form. DOT-order voucher ≥$75 (transferable, 1yr validity,
  on request, program to 2027-04-29; $90M pool). Voucher request redirect
  currently 404s — verify path.
- **Delta** (PRIMARY, eff. 2024-10-24): commitments — meals at 3h+, hotel
  + ground for overnight (or reimburse reasonable costs) for controllable
  disruptions; reimbursement form (US/Canada residents); refunds 7
  business days (card); bag-fee refund 12h dom. Discretionary (NOT
  entitlement): gift cards/credits/miles at agent discretion.
- **DOT dashboard** (all rows via excerpts, page 403s — verify in
  browser): all large carriers commit to meals at 3h controllable; Delta
  + JetBlue commit hotel/transport + partner rebooking, Southwest no
  partner rebooking; **no carrier commits cash for delays**.

## Human re-verification queue (priority order)
1. Azure DOCX (authoritative ladders/deadline) 2. All Google Cloud pages
(fetch truncated) 3. Southwest CSP PDF + voucher-form 404 4. DOT dashboard
rows 5. AT&T consumer terms + tower count 6. Xfinity credit caps 7.
Marriott welcome-gift amounts + midscale row 8. Cloudflare SLA §10 9.
Time-sensitive: Atlassian (eff. 4/2026), Cloudflare (4/2026), JetBlue
points table (changed early 2026).

(Full YAML records with every field and source URL preserved in the
research-agent transcript of 2026-10-19; key URLs: aws.amazon.com/*/sla,
cloud.google.com/*/sla, azure.cn mirrors + microsoft.com/licensing DOCX,
atlassian.com/legal/sla, cloudflare.com/enterprise_support_sla,
att.com/support/smallbusiness/article/smb-my-account/000107635,
xfinity.com/support/articles/check-service-outage + xfinity-customer-
commitment, marriott.com/loyalty/member-benefits/guarantee.mi,
jetblue.com/customer-assurance/*, support.southwest.com helpcenter +
transportation.gov southwest-order-2023-12-11, delta.com/us/en/legal/
customer-commitment, transportation.gov airline dashboard.)

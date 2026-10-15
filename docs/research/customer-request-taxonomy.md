# Customer Request Taxonomy — Research Report

> Produced by a web-research pass (2026-10-15) to ground KarenBot's case
> categories in actual complaint-volume data instead of guesses. Primary
> sources where fetchable; several government pages (DOT, CFPB/FTC PDFs)
> returned 403/binary, so some figures come from secondary legal/industry
> summaries and are marked. Re-verify before quoting externally.
>
> Evidence tiers: A = government volume data · B = survey/industry data with
> methodology · C = app-review/vendor analysis · I = inference.

## Top 3 insights applied to the product

1. **Airline ranking is refund-first, not missed-flight-first.** DOT's top
   categories are refunds (29.1% of cases Jan–Jun 2026) and flight problems
   (cancellations/delays), then baggage (15%). Missed-flight recovery is
   real but evidence-thin (the "flat tire rule" is unwritten discretionary
   policy) — it belongs mid-list, not first. Delay compensation is purely
   discretionary in the US (DOT withdrew the proposed compensation rule
   Nov 17, 2025; automatic refunds for cancellations/significant changes
   in force since Oct 28, 2024) — "refund I'm legally owed" and "goodwill
   for a delay" need different scripts.
2. **Fees are the connective tissue across industries.** Hotels: 37% of
   travelers hit hidden fees (Consumer Reports 2023); AHLA calls hidden
   fees the #1 guest complaint. Delivery: 55% skip delivery over fees.
   Rideshare: 29% cite unfair cancellation fees. Telecom: 67% considered
   switching over hidden charges. Every industry list needs a first-class
   fee-dispute entry.
3. **Memberships are embedded everywhere; financial scope is narrow.**
   Uber One / DashPass / Prime cancellation+refund belongs in rideshare,
   delivery, and e-commerce (FTC: $2.5B Amazon Prime settlement 9/2025;
   FTC v. Uber One 4/2025). In CFPB 2024 data, 85% of complaints are
   credit reporting and 7% debt collection — both excluded — leaving a
   narrow usable financial set: charge disputes, fraud reimbursement,
   fee/overdraft waivers, rewards restoration, frozen-account release.

## Per-industry ranked findings (abridged)

### Airlines (tier A, DOT via secondary summaries)
| Period | Total | Refunds | Flight problems | Baggage |
|---|---|---|---|---|
| 2020 | 102,560 | 89,518 (87.3%) | n/a | n/a |
| 2022 | 77,656 | 19,983 (25.7%) | 24,647 (31.7%) | 12,007 (15.5%) |
| Jan–Jun 2026 | 43,184 | 12,557 (29.1%) | 9,477 (21.9%) | 6,459 (15.0%) |

H1-2026 flight problems: 3,744 cancellations, 2,991 delays, 991 missed
connections, 462 tarmac delays. Caveats: DOT changed counting methodology
twice since 2023; no category data June 2023–July 2025; since ACERS
(8/2025) passengers self-select categories. No US volume data exists for
missed-flight recovery or expired credits (best: CHOICE Australia — 21%
unable to use vouchers, 25% saw them expire).

### Credit cards / banks (CFPB 2024, tier A via law-firm summaries)
~3.19M complaints: credit reporting 85% (excluded), debt collection 7%
(excluded), credit cards 3%, checking/savings 2%. Card issues: statement
purchases, fees and interest; rewards complaints up 70% vs pre-pandemic.
Checking: unauthorized/fraud transactions, frozen/closed accounts,
overdraft fees.

### Telecom/ISP
FCC categories: billing largest, then availability (volume data old —
2016 breakdown). Reviews.org 2025 (tier B): 71–73% saw price increases;
67% switch-considered over hidden fees; 88% want all-in pricing. Consumer
Reports: 70% who haggled, 80% got concessions.

### E-commerce/retail (FTC 2024, tier A)
6.5M reports; online shopping 383K fraud reports (#2 after imposters).
Top asks: never delivered, damaged/defective, wrong item, refund-not-
received after return, return denied, price adjustment, warranty, late
shipping. Returns: ~$706–850B/yr (NRF/Appriss, conflicting bases).

### Rideshare (tier B/C)
Upgraded Points 2023 (n=3,164): surge 65%, no drivers 36%, unfair
cancellation fees 29%. Uber 1-star reviews: surge/hidden fees 28%,
support 22%. FTC v. Uber: up to 32 actions across 23 screens to cancel
Uber One.

### Delivery apps (tier C)
Review mining: missing/wrong items 22%, delivery time 18%, refund/support
15%, hidden fees 12%. Distinct asks: inadequate credits ("$3 for a $30
order"), refunded-as-credit-not-cash, refund-abuse flags, slow refunds.

### Hotels (tier B)
Hidden fees: 37% hit (CR 2023); #1 guest complaint (AHLA); 68% unaware of
resort fees at booking (J.D. Power). FTC junk-fee rule effective 5/2025
for lodging. No volume data for walking/overbooking.

### Subscriptions
FTC: ~70 negative-option complaints/day (2024). Click-to-cancel vacated
7/2025 (procedural); FTC restarted rulemaking 3/2026; state auto-renewal
laws carry the load. Bankrate 2022: 51% hit unexpected subscription
charges; 34% found cancellation hard.

### Cross-industry request verbs (inferred ranking)
refund/reverse charge · fee waiver · billing-error fix · cancel without
penalty · price adjustment · replace/reship · goodwill credit · restore
points/miles · escalate · reinstate account.

## Exclusions confirmed (regulated — stay out)
Credit reporting/repair (85% of CFPB volume), debt collection/settlement,
loan servicing, insurance claims, medical billing, imposter-scam/crypto
"recovery" (card-network fraud disputes stay in scope as bank disputes).
Future verticals, not exclusions: auto sales/repair (#1 CFA category ten
years running), landlord-tenant, contractors.

## Gaps in public data
DOT subcategories unpublished (reservations, fares, frequent-flyer);
missed-flight/expired-credit volume nonexistent; FCC breakdown stale
(2016); FTC subcategory CSVs unfetched; rideshare/delivery rest on 2023
surveys and opaque review mining; restaurants thinnest (mostly inference).
Next steps: pull FCC data center + FTC Explore Data CSVs directly; mine
KarenBot's own "Something else…" intake entries once live (self-improving
taxonomy from real demand).

## Sources
DOT ATCR (Nov 2025, 403 on fetch) · DOT Dec-2022/full-2022 release ·
AirAdvisor US complaint stats · Eckert Seamans DOT-2022 summary · DOT
automatic-refund final rule · TPG (compensation-rule withdrawal; flat-tire
policy) · CHOICE voucher survey · Goodwin + Hudson Cook CFPB-2024
summaries · CFPB 2024 Consumer Response Annual Report · KPMG FTC
Data Book 2024 summary · FTC Sentinel Data Book 2024 · FTC unreceived-
goods spotlight (2020) · CFA 2023/2024 complaint reports · ConsumerAffairs
FCC database (2016) · FCC informal-complaint guide · Benton/Reviews.org
2025 trust survey · Consumer Reports haggling + resort fees · Upgraded
Points rideshare survey (2023) · unstar.app review analyses (2026) ·
Chatmeter via Restaurant Dive (2025) · Chargebacks911 · Chain Store
Age/Just Style returns data · Barnes & Thornburg junk-fee rule · J.D.
Power 2025 hotel study (via TravelPulse/Hotel Dive) · Fenwick click-to-
cancel vacatur · Greenberg Traurig ANPRM (3/2026) · ABC7 Amazon/FTC
settlement · Fortune FTC-v-Uber · ConsumerAffairs click-to-cancel revival.

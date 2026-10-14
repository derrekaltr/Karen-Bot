# KarenBot — Legal & Operational Risk Memo: Corporate Pushback from Target Companies

> **DISCLAIMER:** This document is research for internal discussion only. It is **not legal advice** and is a template/analysis for informational purposes. **Licensed counsel must review KarenBot's structure, terms, marketing, and outbound-communication design before launch.** Consult with a qualified attorney for legal advice specific to your situation.
>
> Prepared: 2026-10-14 · Scope: US consumer platform; AI agent emails official customer-service channels of large companies (airlines, rideshare, fast food, card issuers) on customers' documented authorization, pursuing refunds/credits/goodwill. Subscription + success fee on verified recoveries. Safety rails assumed as designed: no fabrication, no litigation threats, no impersonation (AI/representative status disclosed), no CAPTCHA/security bypass, rate-limited messaging, official channels only, customer approval for binding settlements, no small-business targets.

---

## 1. Realistic corporate responses, ordered by likelihood

### 1.1 Silent suppression (near-certain for at least some targets)

The most likely response is not legal at all — it is operational and invisible:

- **Email filtering/blocklisting.** Support inboxes at scale run spam and pattern detection. A sending domain that emits thousands of structurally similar complaint emails will get reputation-scored down or blocked outright — silently. The customer never learns why follow-ups go unanswered. This is the de facto suppression mechanism and it requires no legal theory, no notice, and carries no risk for the company.
- **Template detection and deprioritization.** Airlines did exactly this with EU261 claim farms: form-letter claims get routed to a slower, more skeptical queue. Expect auto-replies like "we are unable to process this request" with no further engagement.
- **"We only deal with the account holder" policies.** Companies are generally free to refuse to negotiate with an agent and insist on hearing from the customer directly (see § 3). Ryanair formalized this for EU261 claims, requiring passengers to claim directly before any third party could be involved ([TravelPulse on AirHelp v. Ryanair](https://www.travelpulse.com/news/airlines/airline-passenger-rights-group-wins-landmark-claims-case-in-europe.html)). In the EU that policy was partially struck down because EU261 is a statutory entitlement; for US *goodwill/discretionary* compensation there is no equivalent statute, so a "customer only" policy is on much stronger footing here.
- **Settling directly with the customer and ignoring KarenBot.** The English Court of Appeal confirmed airlines may pay the passenger directly and bypass the claims handler entirely ([HFW, "Airlines vs claims agencies: the EU261 fight continues," Nov. 2019](https://www.hfw.com/Airlines-vs-claims-agencies-the-EU261-fight-continues-November-2019)). Expect the same move in the US: a target company that wants to resolve a claim will often email or call the customer directly — which complicates success-fee verification (design implication: fee terms must capture recoveries obtained "as a result of" KarenBot's outreach, not only recoveries paid through KarenBot).

**Assessment: high likelihood, low legal risk, high operational risk.** This is the main threat to the business model, not litigation.

### 1.2 ToS-based action against the *customer* (likely at some scale)

Most target companies' consumer ToS contain clauses about account access, automated activity, or abusive conduct. Realistic actions:

- Flagging or closing the customer's loyalty/app account (airlines and rideshare are most aggressive here — airlines routinely audit frequent-flyer accounts and have terminated accounts for perceived abuse of compensation/goodwill programs).
- Refusing future goodwill compensation to customers identified as using a claims service ("this account has exhausted goodwill adjustments").
- Requiring identity verification or a signed statement from the customer before processing anything.

Note the asymmetry: the ToS relationship is between the company and the **customer**, not KarenBot. The company's cleanest lever is punishing its own customer, which is reputationally awkward for them but real. KarenBot must disclose this risk in its own ToS and onboarding ("Using KarenBot may affect your account standing with the company"), both for honesty and to blunt customer claims against KarenBot if an account is closed.

**Assessment: moderate–high likelihood once volume is noticeable; the damages flow to customers, creating churn and negative reviews rather than direct liability — unless KarenBot failed to warn.**

### 1.3 Cease-and-desist letters to KarenBot (likely from 1–3 companies within the first year at scale)

Expect C&Ds asserting a grab-bag: trademark, tortious interference, CFAA, state computer-trespass, ToS breach, "harassment of our employees." Most are sent to intimidate a pre-revenue startup, not as litigation precursors. The correct posture is a prepared, lawyer-reviewed response template that:

1. Documents customer authorization (produce the signed letter of authorization),
2. Reiterates the safety rails (truthful, disclosed, rate-limited, official channels only),
3. Offers a per-company accommodation channel (see § 4.5),
4. Declines to stop operating on behalf of authorized customers, while honoring any technical access revocation.

### 1.4 Actual legal theories they could try (tail risk — be accurate about strength)

| Theory | Strength against KarenBot as designed | Notes |
|---|---|---|
| **Breach of ToS / breach of contract** | **Weak vs. KarenBot; moderate vs. customer** | KarenBot typically hasn't agreed to the target's ToS. Emailing a public support address is not use of "the service" in most ToS. The customer may have agreed to clauses barring agents or automation; remedy is usually account action, not damages. |
| **CFAA / state computer-trespass** | **Very weak** | Sending email to a publicly held-out support inbox is not "access without authorization." *Van Buren v. United States* (2021) narrowed the CFAA to a "gates-up-or-down" inquiry and rejected criminalizing ToS-style circumstance-based restrictions ([Cooley on Van Buren](https://www.cooley.com/news/insight/2021/2021-06-09-us-supreme-court-computer-fraud-abuse-act-van-buren)); *hiQ v. LinkedIn* on remand reaffirmed that accessing publicly available systems is not unauthorized access even if ToS prohibit it ([White & Case](https://www.whitecase.com/publications/article/web-scraping-website-terms-and-cfaa-hiqs-preliminary-injunction-affirmed-again)). **Caveat:** this changes if KarenBot ever (a) logs into the customer's account on the target's site, (b) continues sending after a technical block or an explicit revocation of authorization directed at KarenBot's infrastructure, or (c) evades blocks by rotating domains/IPs. *Post-revocation continuation is where CFAA/trespass-to-chattels theories regain life* (cf. *Facebook v. Power Ventures*, 9th Cir. 2016). Never rotate around a block. |
| **Tortious interference (with contract or prospective advantage)** | **Weak** | KarenBot acts as the customer's authorized agent asserting the customer's own claims against the company — that is the opposite of inducing breach. Interference also generally requires improper means; truthful, disclosed advocacy is not improper. Becomes colorable only if KarenBot used deception or harassment. |
| **Trademark infringement / false endorsement** | **Weak if handled correctly, but the most likely *actual* C&D topic** | Nominative fair use covers "we help you get refunds from Delta." Danger zones: using logos, company names in ad keywords/landing pages implying partnership ("KarenBot for Uber" pages), or anything suggesting affiliation. Mitigate with plain-text references, no logos, prominent "not affiliated with or endorsed by" disclaimers. |
| **State UDAP / unfair-competition counterclaims** | **Weak on the merits; non-trivial as a harassment vector** | A target could claim KarenBot deceives *its* customers (overpromising recoveries) or floods channels unfairly. Defense is Section 5 hygiene on KarenBot's own marketing (§ 4.6) and documented truthfulness of outbound mail. California UCL § 17200 is broad enough that a motivated GC could file; expect it as leverage, not a winner. |
| **Defamation / trade libel** | **Very weak given no-fabrication rail** | Only if the agent sends false factual assertions about the company. The no-fabrication guarantee plus human-reviewable claim provenance (every factual assertion traced to a customer-provided document) is the defense. Log everything. |
| **"Harassment" / nuisance theories** | **Very weak if rate limits hold** | Scheduled, spaced, professional follow-ups to a support inbox are ordinary commerce. Keep per-case and per-company global rate caps and a hard stop on "do not contact us further about this matter" per case. |

**Mass-arbitration dynamics — a double-edged sword worth understanding.** Most targets (Uber, Amex, airlines, DoorDash-style platforms) have consumer arbitration clauses with class waivers. Two implications:

1. If a target wanted to pursue customers formally, those clauses often channel disputes to arbitration — expensive and unattractive for the company against its own customers; essentially never happens over refund requests.
2. More interesting: aggregated customers with similar grievances are structurally similar to a **mass-arbitration play** — the thing companies fear most ([O'Melveny, "Mass Arbitrations in 2025"](https://www.omm.com/insights/alerts-publications/mass-arbitrations-in-2025-key-legal-shifts-every-company-should-know); [Holland & Knight on the mass-arbitration surge](https://www.hklaw.com/en/insights/publications/2025/02/shielding-against-the-mass-arbitration-surge-strategies)). KarenBot should **not** market itself as a mass-arbitration aggregator (that drifts toward law-practice territory and radically escalates corporate hostility), but companies' awareness that unresolved claims can be referred to plaintiff firms that do mass arbitration is quiet background leverage. Companies have responded by rewriting arbitration clauses (bellwether/batching, fee-shifting, pre-filing conferences; AAA revised mass-arbitration fee schedules). Takeaway: targets are already spending heavily on claim-volume defense; a polite email-negotiation service is a *less* threatening alternative they may eventually prefer to feed.

---

## 2. Precedents and analogues

### 2.1 DoNotPay — the closest comp, and the lesson is about *marketing*, not the activity

- **FTC action (Sept. 2024, Operation AI Comply; final order early 2025):** The FTC charged DoNotPay over **deceptive advertising claims** — that its "robot lawyer" could substitute for a human lawyer and "generate perfectly valid legal documents," claims DoNotPay never tested or validated with attorneys. Settlement: **$193,000** monetary relief, consumer notice to 2021–2023 subscribers, and a prohibition on lawyer-equivalence claims without evidence ([FTC press release](https://www.ftc.gov/node/87474); [Bloomberg Law](https://news.bloomberglaw.com/bloomberg-government-news/ftc-settles-with-donotpay-as-part-of-ai-enforcement-operation); [Slashdot/FTC final order coverage, Feb. 2025](https://tech.slashdot.org/story/25/02/11/1932223/)). **Crucially, the FTC did not act against the practice of sending automated demand/complaint letters.** The violation was unsubstantiated AI-performance and "lawyer replacement" advertising.
- **Faridian v. DoNotPay (N.D. Cal., filed 2023, settled 2024):** Private class action alleging **unauthorized practice of law (UPL)** and shoddy document drafting; settled on undisclosed terms ([ABA Journal](https://www.abajournal.com/news/article/robot-lawyer-donotpay-reaches-settlement-in-suit-alleging-it-is-neither-a-robot-nor-a-lawyer); [complaint](https://storage.courtlistener.com/recap/gov.uscourts.cand.410868/gov.uscourts.cand.410868.1.0.pdf)).
- **Lesson for KarenBot:** both actions trace to the word "lawyer." A refund-advocacy service that never uses "lawyer," "legal advice," "legal documents," or lawyer-equivalence claims — and substantiates its recovery-rate statistics — avoids the entire DoNotPay failure mode. Negotiating a consumer refund is not the practice of law; drafting "legal documents" and advertising legal competence is where UPL lives.

### 2.2 AirHelp and the EU261 claim farms — the playbook for airline pushback

- Airlines wrongfully rejected ~25%+ of valid EU261 claims (AirHelp data, 2016–2018), which is what created the claim-agency market ([The Points Guy](https://thepointsguy.com/news/airhelp-us-airlines-wrongfully-rejecting-25-of-eu-261-compensation-claims/)).
- Airline countermeasures: Ryanair required passengers to claim **directly first** and refused third-party submissions; AirHelp defeated that policy in a Dutch court because EU261 is a statutory right ([TravelPulse](https://www.travelpulse.com/news/airlines/airline-passenger-rights-group-wins-landmark-claims-case-in-europe.html)); Belgian courts also ordered Ryanair to pay claim companies representing passengers ([Aviation24.be](https://www.aviation24.be/airlines/ryanair/ryanair-sentenced-to-pay-compensations-to-passengers-for-flights-cancelled-in-autumn-2017/)). Ryanair also ran PR campaigns against "claims chasers" charging up to 50% fees ([Travel Weekly](https://travelweekly.co.uk/news/ryanair-fails-in-court-bid-for-injunction-against-agent)).
- English Court of Appeal: airlines may settle directly with the passenger and bypass the handler ([HFW, Nov. 2019](https://www.hfw.com/Airlines-vs-claims-agencies-the-EU261-fight-continues-November-2019)).
- **US translation:** most of what KarenBot pursues (goodwill credits, discretionary refunds) is **not** statutory, so the AirHelp court victories do not port over. Expect US companies to be able to maintain "customer only" policies for discretionary compensation. Exception: **DOT-regulated refunds** (cancelled/significantly changed flights, 14 CFR Part 260 automatic-refund rules) are statutory-ish entitlements where a regulator-complaint escalation path has real teeth.

### 2.3 Trim / Truebill (Rocket Money) / BillShark — bill negotiation survived

- These services have negotiated with telecoms/utilities for a decade on success fees of 15–60% of first-year savings without facing enforcement for the negotiation activity itself ([Rocket Money fee disclosures](https://help.rocketmoney.com/en/articles/6676442-bill-negotiations-faq); [Trim review](https://michaelsaves.com/save-money/trim-review/)). Providers' pushback was operational (refusing to talk to agents, requiring account-holder verification), not legal.
- **Cautionary note:** BillShark's terms reportedly allowed agents to **pretend to be the account holder** ([Atlanta News First, July 2026](https://www.atlantanewsfirst.com/2026/07/10/online-bill-negotiators-promise-savings-require-personal-data-access/)) — exactly what KarenBot's no-impersonation rail correctly forbids. Impersonation is the single practice most likely to convert operational friction into fraud/UDAP exposure. KarenBot's disclosed-agent model is materially safer than the incumbent norm.
- Friction pattern to expect: companies demand the account holder on the line / account-holder verification. KarenBot's email-only model avoids phone verification walls but will hit "please confirm from the email on file" demands — design for customer-confirmation loops (one-click "yes, KarenBot represents me" relays from the customer's own mailbox, which the Gmail OAuth integration enables cleanly).

### 2.4 Credit repair (CROA) and debt settlement — the regulated-perimeter warning

- **CROA** (15 U.S.C. § 1679 et seq.) covers anyone paid to improve "any consumer's credit record, credit history, or credit rating" — expressly **or impliedly**. It bans advance fees before full performance, mandates written contracts, 3-day cancellation, and disclosures; it is strict liability and a plaintiff-bar favorite ([Foley overview](https://help.foley.io/hc/en-us/articles/21309999966483); [VantageScore summary](https://vantagescore.com/education/blog/understand-your-rights-under-the-credit-repair-organizations-act)).
- **Trap for KarenBot:** disputing a **card issuer** charge can drift into CROA territory if marketing ever implies removing derogatory marks, fixing chargebacks on a credit report, or "improving your standing." Keep card-issuer work strictly framed as *refund/fee-reversal requests on the account*, never anything touching credit reporting. Also avoid coaching customers on FCRA disputes. Similarly, the **Telemarketing Sales Rule debt-relief advance-fee ban** and state debt-settlement statutes are out of scope only because KarenBot excludes debt — keep that exclusion hard-coded, including "negotiate down my balance" requests.
- The success-fee-on-recovery model is lawful in the unregulated general-consumer-claims space, but § 3 lists state regimes that regulate success-fee claim representation in adjacent verticals.

### 2.5 Google restricted scopes / CASA — the real chokepoint nobody sues over

Gmail API scopes are **restricted scopes**: KarenBot must pass Google's OAuth app verification plus an **annual CASA security assessment** (OWASP ASVS-based, Tier 2/3, by an authorized lab — Leviathan, TAC, DEKRA; typically low-thousands of dollars/year), with yearly revalidation. Failure or policy violation means API access revocation — an instant kill switch for the entire product ([Google restricted scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification); [DeepStrike CASA 2025 guide](https://deepstrike.io/blog/google-casa-security-assessment-2025); [Leviathan CASA program](https://leviathansecurity.com/programs/google-casa-cloud-application-security-assessment)).

Also note Google's **Limited Use policy** for restricted-scope data: Gmail data may only be used to provide user-facing features; no ads, no unrelated model training without explicit consent. A target company's most effective attack might be a complaint to Google alleging KarenBot abuses Gmail scopes. Mitigation: minimal scopes (prefer `gmail.send` + narrow read of the case thread over full `gmail.readonly`), spotless Limited Use compliance, CASA scheduled months before launch (lead times run 4–12 weeks).

### 2.6 Email deliverability as de facto suppression

Bulk/automated senders face Gmail/Yahoo-style sender requirements (SPF, DKIM, DMARC, one-click unsubscribe for bulk, spam-rate thresholds) and corporate-side gateways (Proofpoint, Mimecast) that will pattern-block. If KarenBot sends **from the customer's own Gmail via OAuth**, each message rides Gmail's reputation and looks like a genuine customer email — far more resilient than a dedicated KarenBot domain, and more honest (it *is* the customer's mailbox, sent by their authorized agent, with the agent disclosed in the body/signature). A dedicated KarenBot domain should still exist for KarenBot's own transactional/notification mail, with full SPF/DKIM/DMARC (p=reject) and subdomain isolation. **Never** spoof or send "as" the customer from non-customer infrastructure.

---

## 3. The authorization / agency angle

### 3.1 Why documented authorization is the load-bearing wall

Everything defensible about KarenBot rests on genuine agency: the customer has appointed KarenBot as agent for a specific claim. A signed, timestamped **Letter of Authorization (LOA)** per case (identifying the customer, the company, the transaction, the scope of authority, and the right to revoke) converts "random bot emailing our support desk" into "the customer's chosen representative," which:

- defeats tortious-interference and harassment framings (agent asserts principal's own claim),
- gives the C&D response real documents to attach,
- satisfies companies that run passenger/customer-confirmation checks (the airline pattern),
- is the factual predicate for the "authorized agent" concepts US law already recognizes (e.g., CCPA authorized-agent requests, FDCPA attorney/representative channels) even where no statute directly governs.

Include in the LOA: authority to *communicate and negotiate* but **not** to bind — settlements require customer approval (already a design rail; mirror it in the legal document). Keep LOAs producible on demand and offer to furnish them proactively on first contact per company.

### 3.2 Companies' right to insist on dealing with the customer

In the US, absent a statute, a company owes no duty to negotiate with anyone's agent about **discretionary** compensation. "We only deal with account holders" is lawful and should be **respected, not evaded** — evasion is what converts weak legal theories into strong ones (post-revocation access, deception). Design response: when a company states a customer-only policy, KarenBot switches to **assist mode** — drafting messages the customer sends from their own mailbox with one-click approval (which the Gmail OAuth architecture supports), plus regulator-complaint escalation where entitlements exist. That preserves the product while removing the legal argument. Note the distinction: for *statutory* entitlements (DOT refund rules, state gift-card/refund statutes), a blanket refusal to process a documented, authorized claim is itself regulator-complaint material.

### 3.3 Regulated verticals and state regimes (perimeter check)

KarenBot already excludes insurance, debt, and medical — correct, because those are exactly the licensed zones:

- **Public adjusters** (insurance claims for a fee): licensed in ~45+ states; fee caps in several (e.g., FL). Any drift into "we'll pursue your insurance claim" requires licensure. Hard exclusion.
- **Debt settlement/adjustment**: TSR advance-fee ban plus state licensing (e.g., NY, IL); negotiating a *balance owed* downward is debt settlement. Refund-of-a-charge ≠ reduction-of-a-debt; keep classifiers that reject balance-reduction requests.
- **CROA**: see § 2.4 — avoid implied credit-improvement claims.
- **UPL (all states)**: no legal advice, no representation in disputes framed as legal claims, no drafting of court/arbitration documents, no fee-sharing with lawyers. If a case needs a lawyer, refer out and stop.
- **Watch-items, likely fine but confirm with counsel:** state "claims adjustment"/collection-agency definitions (KarenBot collects *for* consumers *from* companies — generally outside collection-agency statutes aimed at consumer-debt collection, but a handful of states define broadly); contingent-fee solicitation rules only bind lawyers; unclaimed-property/refund-recovery "finder" statutes in a few states cap fees for locating funds (distinct activity, but map it).
- **Success fee mechanics:** charge only after recovery is verified (also the FTC-friendly posture — advance-fee bans across CROA/TSR/debt-relief signal regulator hostility to fees before results; KarenBot's post-recovery success fee is the safe side of that line). Disclose the fee percentage conspicuously pre-enrollment.

---

## 4. Concrete mitigations, ranked by importance

1. **Agency documentation + "respect the refusal" channel policy (highest leverage).** Per-case signed LOA; per-company policy registry (preferred channel, known customer-only policies, known "do not contact" states); automatic switch to customer-sends-it assist mode on refusal; hard stop per case on explicit do-not-contact; never rotate domains/IPs around a block. This single bundle neutralizes CFAA-revival, tortious interference, and harassment theories simultaneously.
2. **Truthfulness architecture in outbound mail.** Every factual assertion machine-traced to a customer document (receipt, confirmation email, screenshot) with provenance logs retained; AI/representative disclosure in every message; no legal threats; immutable audit log per case. This is the defamation/fraud/UDAP shield and your C&D exhibit A.
3. **Marketing hygiene — the DoNotPay lesson.** Never "lawyer," "legal advice," "legal team," or lawyer-equivalence claims. Substantiate every recovery statistic ("average recovery $X" requires real, current data — FTC Section 5 and the final DoNotPay order show unsubstantiated AI-performance claims are the enforcement target). Clear fee disclosure; easy cancellation (ROSCA/click-to-cancel compliance for the subscription); "not affiliated with [Company]" disclaimers; no target-company logos; careful keyword-ad usage of brand names (bid on them if you like — pure keyword bidding is generally lawful — but ad copy must not imply affiliation).
4. **Entity structure + insurance.** Delaware C-corp (or similar) with clean separation; **E&O/professional liability** covering negotiation errors, **media/cyber liability** covering defamation and data claims, and **D&O** before taking institutional money. Expect insurers to ask DoNotPay-flavored questions; the safety rails and truthfulness architecture are your underwriting story.
5. **KarenBot's own ToS: arbitration clause + class waiver + mass-arbitration-resilient design** (bellwether/batching procedure, pre-filing conference, small-claims carve-out — the 2025 state of the art per [O'Melveny](https://www.omm.com/insights/alerts-publications/mass-arbitrations-in-2025-key-legal-shifts-every-company-should-know) and [Holland & Knight](https://www.hklaw.com/en/insights/publications/2025/02/shielding-against-the-mass-arbitration-surge-strategies)); plus: customer warranty that facts provided are true, account-action risk disclosure (§ 1.2), success-fee definition covering direct-to-customer payouts caused by KarenBot's outreach, agency appointment + revocation terms, and a UPL disclaimer ("KarenBot is not a law firm and does not provide legal advice").
6. **Google OAuth/CASA readiness as a launch-critical path.** Minimal restricted scopes; Limited Use compliance; CASA audit booked 3+ months pre-launch; annual revalidation calendared; incident-response plan for a Google policy complaint from a target company. ([Google](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification); [DeepStrike](https://deepstrike.io/blog/google-casa-security-assessment-2025).)
7. **Email infrastructure.** Send case emails from the customer's own Gmail via OAuth (reputation + authenticity); dedicated KarenBot domain with SPF/DKIM/DMARC p=reject for everything else; per-company and global rate limits with jitter and human-plausible cadence; deliverability monitoring per target company as an early-warning system for silent blocking.
8. **Regulator-escalation path (legally protected, high leverage).** When a documented entitlement is stonewalled: DOT complaints for airline refunds, CFPB complaints for card issuers, state AG consumer complaints, BBB. Filing truthful regulator complaints on a customer's behalf (or teeing them up for the customer to file) is protected petitioning activity (Noerr-Pennington-adjacent) and cannot support interference/harassment claims. It is also the pressure valve that keeps negotiations honest — companies answer regulator complaints at a far higher rate than inbox email. Keep complaint content strictly factual.
9. **Per-company intelligence and relationship track.** Long-term, the AirHelp/Rocket Money pattern suggests some targets eventually prefer a structured intake from a reliable intermediary over chaotic inbox volume. Maintain a path to formal channel agreements; in the medium term, a company offering KarenBot a dedicated intake process is a win, not a threat.

---

## 5. Sued vs. blocked — summary table, and the top five actions

### What gets us sued vs. what just gets us blocked

| Conduct | Likely consequence | Severity |
|---|---|---|
| Polite, truthful, disclosed, rate-limited emails to public support inboxes with LOA | Blocked/filtered at worst; mostly just slow responses | Operational only |
| High-volume templated claims from one domain | Silent blocklisting; "unable to process" auto-replies | Operational |
| Customer uses KarenBot; company notices | Customer account flags/closures (airlines, rideshare most likely) | Customer churn; disclose risk upfront |
| Using company names in plain text marketing | Occasional trademark C&D; resolvable with disclaimers | Low |
| Using logos / implying partnership / "KarenBot for Delta" landing pages | Trademark suit becomes credible | **Sue-able — avoid** |
| Continuing to email after explicit, specific revocation/block; rotating domains/IPs to evade | Revives CFAA/trespass + harassment theories (*Power Ventures* posture) | **Sue-able — never do** |
| Any impersonation (posing as the customer without disclosure) | Fraud/UDAP exposure + platform bans | **Sue-able — already prohibited by design** |
| Fabricated facts or legal threats in outbound mail | Defamation/extortion-adjacent claims; existential | **Sue-able — already prohibited by design** |
| "AI lawyer" / lawyer-equivalence / unsubstantiated recovery-rate marketing | FTC Section 5 action, UPL class action (the DoNotPay double) | **Sue-able — avoid in all copy** |
| Advance fees or drift into insurance/debt/credit-repair verticals | CROA/TSR/state licensing enforcement | **Sue-able — keep exclusions hard-coded** |
| Logging into target-company systems with customer credentials, scraping behind login, CAPTCHA bypass | Real CFAA/ToS exposure | **Sue-able — out of design, keep it out** |

### Five highest-leverage pre-launch actions

1. **Build the agency + audit backbone:** per-case signed LOA, provenance-logged outbound mail, immutable case logs, and the "respect refusal → assist mode" switchover. This is simultaneously the legal defense file and the C&D response kit.
2. **Scrub all marketing and product copy** of lawyer/legal language and unsubstantiated performance claims; stand up a substantiation file for every statistic before it ships. (Direct DoNotPay lesson — the only enforcement a comparable company actually suffered.)
3. **Book the Google CASA assessment and restricted-scope verification now** (3+ month lead), with minimal scopes and Limited Use compliance — API revocation is the only true kill switch.
4. **Ship KarenBot's own ToS with arbitration + class waiver + mass-arb procedures, customer truth-warranty, account-risk disclosure, and a success-fee definition that captures direct-to-customer payouts** (the bypass-the-agent settlement pattern is documented airline behavior).
5. **Bind E&O + media/cyber insurance and pre-draft the C&D response template with counsel,** plus the regulator-escalation playbook (DOT/CFPB/state AG) so stonewalling has a protected, scripted answer.

---

## Sources

- FTC, [DoNotPay settlement — Operation AI Comply (Sept. 2024)](https://www.ftc.gov/node/87474); [Bloomberg Law coverage](https://news.bloomberglaw.com/bloomberg-government-news/ftc-settles-with-donotpay-as-part-of-ai-enforcement-operation); [final order coverage, Feb. 2025](https://tech.slashdot.org/story/25/02/11/1932223/); [Gigazine settlement summary](https://gigazine.net/gsc_news/en/20240927-ftc-sued-deceptive-ai-claims)
- [ABA Journal — Faridian v. DoNotPay settlement](https://www.abajournal.com/news/article/robot-lawyer-donotpay-reaches-settlement-in-suit-alleging-it-is-neither-a-robot-nor-a-lawyer); [complaint (CourtListener)](https://storage.courtlistener.com/recap/gov.uscourts.cand.410868/gov.uscourts.cand.410868.1.0.pdf)
- [HFW — Airlines vs claims agencies: the EU261 fight continues (Nov. 2019)](https://www.hfw.com/Airlines-vs-claims-agencies-the-EU261-fight-continues-November-2019)
- [The Points Guy — AirHelp: US airlines wrongfully rejecting 25% of EU261 claims](https://thepointsguy.com/news/airhelp-us-airlines-wrongfully-rejecting-25-of-eu-261-compensation-claims/)
- [TravelPulse — AirHelp wins landmark claims case vs. Ryanair policy](https://www.travelpulse.com/news/airlines/airline-passenger-rights-group-wins-landmark-claims-case-in-europe.html); [Aviation24.be — Belgian court orders Ryanair to compensate claim companies](https://www.aviation24.be/airlines/ryanair/ryanair-sentenced-to-pay-compensations-to-passengers-for-flights-cancelled-in-autumn-2017/); [Travel Weekly — Ryanair vs. claims chasers](https://travelweekly.co.uk/news/ryanair-fails-in-court-bid-for-injunction-against-agent)
- [Cooley — Van Buren narrows the CFAA (June 2021)](https://www.cooley.com/news/insight/2021/2021-06-09-us-supreme-court-computer-fraud-abuse-act-van-buren); [White & Case — hiQ v. LinkedIn on remand](https://www.whitecase.com/publications/article/web-scraping-website-terms-and-cfaa-hiqs-preliminary-injunction-affirmed-again)
- [O'Melveny — Mass Arbitrations in 2025](https://www.omm.com/insights/alerts-publications/mass-arbitrations-in-2025-key-legal-shifts-every-company-should-know); [Holland & Knight — Shielding against the mass-arbitration surge (Feb. 2025)](https://www.hklaw.com/en/insights/publications/2025/02/shielding-against-the-mass-arbitration-surge-strategies); [Darrow — Mass arbitration trends](https://www.darrow.ai/resources/mass-arbitration-trends)
- [Google — Restricted scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification); [DeepStrike — Google CASA 2025](https://deepstrike.io/blog/google-casa-security-assessment-2025); [Leviathan — CASA program](https://leviathansecurity.com/programs/google-casa-cloud-application-security-assessment)
- [Foley — FCRA and CROA requirements](https://help.foley.io/hc/en-us/articles/21309999966483); [VantageScore — CROA rights overview](https://vantagescore.com/education/blog/understand-your-rights-under-the-credit-repair-organizations-act)
- [Rocket Money — Bill Negotiations FAQ (fees)](https://help.rocketmoney.com/en/articles/6676442-bill-negotiations-faq); [MichaelSaves — Trim review](https://michaelsaves.com/save-money/trim-review/); [Atlanta News First — bill negotiators and account-holder impersonation (July 2026)](https://www.atlantanewsfirst.com/2026/07/10/online-bill-negotiators-promise-savings-require-personal-data-access/)

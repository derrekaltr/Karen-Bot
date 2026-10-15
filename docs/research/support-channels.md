# Verified Support-Channel Address Book — Research (2026-10-15)

> Every row requires HUMAN VERIFICATION before becoming sendable (policy
> engine enforces verified=True). Tags: OFFICIAL_PAGE / ELLIOTT / OTHER.
> Many official pages 403'd the fetcher; rows marked (snippet) came from
> official-domain search text. Elliott pages carry their own last-verified
> dates. NOTHING here was inferred; known-bad addresses are listed as
> do-not-seed.

## Cross-cutting findings
- No company page found states a third-party-representative policy; the
  only explicit third-party rules are regulator-side (DOT, CFPB below).
- **AA executive emails reportedly bounce/route unmonitored since ~Jan
  2026 (per Elliott) — use AA's web form first.**
- Big-company reality: email is mostly DEAD as a public channel — AA,
  Delta, United, Southwest, JetBlue, Uber, Amazon, Amex, McDonald's,
  Chipotle, Comcast all offer form/app flows, not public complaint
  emails. Executive emails (Elliott-sourced) are the written-channel
  fallback; web-form support is a needed channel type.
- Do-NOT-seed (aggregator-only, unverified): dearjetblue@jetblue.com,
  support@uber.com, we_can_help@comcast.com; ecr-replies@amazon.com may
  be outbound-only.

## Per-company (abridged rows; full provenance in research transcript)

**American Airlines** — form: aa.com/customerrelations (ack 30d / resolve
60d); US email: none (UK-only International.CustomerRelations@aa.com — do
not use for US); exec (ELLIOTT 2026-08-27, BOUNCE WARNING):
kim.cisek@aa.com, heather.garboden@aa.com, robert.isom@aa.com; postal:
Customer Relations, P.O. Box 619619, DFW Airport, TX 75261-9616.

**Delta** — form: delta.com/us/en/need-help/overview (Comment & Complaint);
refunds: /change-cancel/cancel-flight?refund-reimbursement=true; email:
none; exec (ELLIOTT 2026-06-03): heidi.gould@delta.com,
kristin.colvile@delta.com, ed.bastian@delta.com; postal: Customer Care,
P.O. Box 20980, Dept 980, Atlanta, GA 30320-2980.

**United** — form: united.com Customer Care (production URL unconfirmed —
only preview host found; VERIFY); baggage-only email:
web-baggage@united.com (ELLIOTT); exec (2026-08-26): K.Freeman@united.com,
b.stoller@united.com, scott.kirby@united.com; postal: Customer Care, 900
Grand Plaza Dr, NHCCR, Houston, TX 77067-4323 (verify).

**Southwest** — form: support.southwest.com/helpcenter/contact-us (old
/contact-us.html 301s); email: none; exec (ELLIOTT 2026-05-16):
michelle.buckley@wnco.com, Tony.Roach@wnco.com, Kevin.McDorman@wnco.com,
bob.jordan@wnco.com; postal: PO Box 36647-1CR, Dallas, TX 75235 (ELLIOTT
only); escalation phone 855-234-4654; written complaints ack 30d/answer
60d per Customer Service Plan.

**JetBlue** — form: jetblue.com/contact-us (per Customer Service Plan);
email: NONE ("Not offered" per Elliott; dearjetblue@ unverified — do not
seed); exec (2026-08-09): steven.olson@jetblue.com,
warren.christie@jetblue.com, j.geraghty@jetblue.com; postal: 27-01 Queens
Plaza North, Long Island City, NY 11101.

**Alaska** — form: alaskaair.com/feedback/general-comments (attachments
allowed); email: customer.care@alaskaair.com (ELLIOTT 2026-08-17; not on
official page — verify); exec: trudy.dobbins@, wayne.newton@,
allen.thieman@, ben.minicucci@alaskaair.com (titles may be stale
post-Hawaiian merger); postal: Customer Care, P.O. Box 68900 - SEAGT,
Seattle, WA 98168-0900.

**Uber** — in-app Help / help.uber.com only; no rider email; exec (ELLIOTT
2026-09-09): dcx@uber.com (Sr Dir Community Ops), dm@uber.com (COO),
dk@uber.com (CEO); postal (LEGAL NOTICES ONLY, arbitration-relevant):
Attn: Legal Dept, 1725 3rd St, San Francisco, CA 94158.

**Amazon** — Help/Contact via account (nodeId=508510); exec emails
(ELLIOTT 2026-06-01): cs-escalations@amazon.com (~24h responses),
ecr-replies@amazon.com (possibly outbound-only — test or skip),
herringtond@amazon.com, ajassy@amazon.com.

**American Express** — secure Message/Chat requires ACCOUNT HOLDER login
(assist-mode significant); Document Upload Center for disputes; postal
(BILLING DOCS ONLY): P.O. Box 981535, El Paso, TX 79998; exec (2026-05-16):
mohammed.badi@aexp.com, howard.m.grosfield@aexp.com, steve.squeri@aexp.com;
regulator: CFPB consumerfinance.gov/complaint, (855) 411-2372.

**McDonald's** — forms: mcdonalds.com/us/en-us/feedback.html +
/contact-us.html; email: none (contact.privacy@us.mcd.com is privacy-only);
exec (2026-08-25): viva.cohen@, alyssa.buetikofer@,
skye.anderson@mcdonalds.com; HQ: 110 N Carpenter St, Chicago, IL 60607.

**Chipotle** — chipotle.com/contact-us ("Contact Support" + Pepper chat),
1-800-CHIPOTLE; email: none (privacy@ is privacy-only); exec (2026-05-29):
sally.evans.murphy@ (PR — weak target), cgarner@, sboatwright@chipotle.com;
HQ: 610 Newport Center Dr #1100, Newport Beach, CA 92660.

**Marriott** — support.marriott.com Contact Us (sign-in; hotel mgmt replies
≤5 business days); email Customer.Care.Resolution@Marriott.com (ELLIOTT but
STALE 2025-09-30 — verify); exec: jennifer.mclennanbrown@, Jodie.larson@,
anthony.capuano@marriott.com; HQ: 7750 Wisconsin Ave, Bethesda, MD 20814.

**Comcast/Xfinity** — xfinity.com/support/contact-us +
/support/svp-contact-form ("Send Xfinity Feedback"); email: none; exec
(ELLIOTT 2026-10-01): cory_harriger@comcast.com,
tom_karinshak@cable.comcast.com, mike_cavanagh@comcast.com; regulator: FCC
consumercomplaints.fcc.gov (provider must respond in 30 days).

## Regulators
- **DOT** (all airlines): transportation.gov/airconsumer/file-consumer-
  complaint; mail: Office of Aviation Consumer Protection, 1200 New Jersey
  Ave SE, Washington DC 20590. Airlines must ack in 30d, respond in 60d.
  Formal third-party complaints (14 CFR 302) "generally filed by attorneys
  or public interest groups."
- **CFPB** (Amex): consumerfinance.gov/complaint. Third-party rules (gold
  for our LOA design): identify yourself clearly; companies may require
  SIGNED WRITTEN PROOF of consumer permission; never submit without
  knowledge+authorization; declare representative relationship; company
  response goes to the consumer's portal, not the submitter.
- **FCC** (Comcast): fcc.gov/complaints.

## Human-verify queue (highest priority)
1. AA form URL + US postal (page 403'd) · 2. United production form URL ·
3. Alaska/Marriott email official status · 4. Southwest Customer Service
Plan + Contract of Carriage for representative language · 5. Every
Elliott executive email before first use (AA's reportedly bounce).

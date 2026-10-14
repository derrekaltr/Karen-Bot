# KarenBot's Moral Code

KarenBot exists to level the playing field between individual consumers and
large corporations — not to squeeze small businesses. These rules are
enforced in deterministic code, not in prompts, so the model cannot be talked
out of them and configuration cannot disable them.

## 1. Punch up, never down

KarenBot only pursues **large enterprises**: national chains, airlines,
rideshare platforms, card networks, big-box retail (Delta, Uber, Chipotle,
McDonald's, American Express, and peers).

- Every company carries a `size_class`: `enterprise`, `mid_market`,
  `small_business`, or `unclassified`.
- **`small_business` (mom-and-pop) is never targetable.** No exceptions.
- **`unclassified` is never targetable** — the safe default for any company a
  human hasn't reviewed is to leave it alone.
- The targetable list ships as `["enterprise"]`. The settings validator
  silently strips `small_business` and `unclassified` if anyone tries to add
  them (`config.NEVER_TARGETABLE_SIZE_CLASSES`).

Enforcement is three independent layers:

| Layer | Behavior | Code |
|---|---|---|
| Case intake | Refuses to create the case | `services.create_case` → `CompanyNotTargetable` |
| Policy engine | Denies any outbound action (`company_not_targetable:*`) | `policy/engine.py` |
| Config | Cannot whitelist protected classes | `config.Settings._enforce_moral_code` |

Covered by `tests/policy/test_moral_code.py` and `tests/policy/test_engine.py`.

## 2. Truth only

No fabricated receipts, facts, policies, or legal claims. Eligibility is
decided by verified, sourced policy rules — never asserted by the model.

## 3. Proportionate pressure

Rate limits, follow-up caps, and minimum waits between messages. Firm is
fine; harassment is not. No litigation threats. If a company says it will
only deal with the customer directly, that channel preference is respected,
not evaded.

## 4. Honest identity

KarenBot always discloses that it is an authorized representative acting with
the customer's documented consent. No impersonating the customer where
disclosure is required, no CAPTCHA or security-control bypass.

## 5. The customer stays in charge

Binding settlements, waivers, and anything irreversible require explicit
per-action customer approval. Authority can be revoked at any moment and the
agent stops.

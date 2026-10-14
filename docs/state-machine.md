# Case State Machine

All transitions go through `karenbot.domain.state_machine.transition()`; the
full legal-transition table lives there and is exhaustively tested in
`tests/unit/test_state_machine.py`.

## Happy path

```
DISCOVERED
  └─ INFO_REQUESTED ──> AWAITING_INFORMATION
  └─ INTAKE_COMPLETE ─┐    └─ INFO_RECEIVED ─┐
                      v                      v
                 ELIGIBILITY_REVIEW ── ELIGIBILITY_CONFIRMED ──> AWAITING_AUTHORIZATION
                      │                                                  │
                      └─ ELIGIBILITY_REJECTED ──> CLOSED_UNSUCCESSFUL    │ AUTHORIZATION_GRANTED
                                                                         v
READY_TO_CONTACT ── CONTACT_INITIATED ──> CONTACTING_COMPANY ── MESSAGE_SENT ──> AWAITING_RESPONSE
                                                                                      │
                     ┌────────────────────────────── REPLY_RECEIVED ─────────────────┘
                     v
                NEGOTIATING ── MESSAGE_SENT ──> AWAITING_RESPONSE (loop)
                     │
                     ├─ OFFER_MADE ──> OFFER_RECEIVED ── OFFER_DECLINED ──> NEGOTIATING
                     │                      │
                     │                      ├─ APPROVAL_REQUESTED ──> AWAITING_CUSTOMER_APPROVAL
                     │                      │         ├─ APPROVAL_GRANTED ──> VERIFYING_RECOVERY
                     │                      │         └─ APPROVAL_DENIED ───> NEGOTIATING
                     │                      └─ OFFER_ACCEPTED ──> VERIFYING_RECOVERY
                     │                                                 │
                     └─ ESCALATION_STARTED ──> ESCALATED               ├─ RECOVERY_VERIFIED ──> RESOLVED
                                                                       └─ RECOVERY_NOT_VERIFIED ─> NEGOTIATING
```

## Global events

- `CUSTOMER_CANCELED`: any active state -> `CANCELED` (customer kill switch /
  authority revocation).
- `CASE_BLOCKED`: any active state -> `BLOCKED` (admin/compliance hold);
  stores the previous status.
- `CASE_RESUMED`: `BLOCKED` -> the stored previous status.
- `NO_RESPONSE_EXHAUSTED`: `AWAITING_RESPONSE` -> `ESCALATED`;
  `ESCALATED`/`NEGOTIATING` -> `CLOSED_UNSUCCESSFUL`.

`RESOLVED`, `CLOSED_UNSUCCESSFUL`, and `CANCELED` are terminal.

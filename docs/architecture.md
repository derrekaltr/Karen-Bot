# KarenBot Architecture

KarenBot is an autonomous AI consumer-recovery platform: customers submit a
dispute, grant scoped authority, and an agent negotiates with the company
over email (chat and voice channels later) until a verified recovery or a
dead end.

## Core principle: propose → authorize → execute

The language model **proposes** actions; deterministic code **authorizes and
executes** them.

```
┌──────────┐  ProposedAction   ┌──────────────┐  ALLOW    ┌──────────┐
│  Agent   │ ────────────────> │ PolicyEngine │ ────────> │ Executor │
│ (LLM)    │                   │ (pure, no IO)│  DENY /   └────┬─────┘
└──────────┘                   └──────────────┘  APPROVAL      │ outbox row
     ^  read-only tools                                        v
     │  (facts, policy,                                 ┌──────────────┐
     │   thread history)                                │ Outbox worker│──> ChannelAdapter
     └──────────────────────────────────────────────────┴──────────────┘    (mock | gmail | chat | voice)
```

- `agent/actions.py` — the `ProposedAction` Pydantic union. The only shape in
  which the model can request anything.
- `policy/engine.py` — pure function `evaluate(action, ctx) -> ALLOW | DENY |
  NEEDS_APPROVAL` implementing: active authorization, verified recipient,
  claim-type allowlist, amount ceilings, rate/frequency limits, duplicate
  detection, sensitive-action approval. Exhaustively unit-tested.
- `workflows/executor.py` — dispatches ALLOWed actions. Resolves recipients
  from the verified `support_channels` table itself (defense in depth: the
  model never names an address).
- Every proposal, verdict, and execution is persisted (`agent_actions`,
  `audit_events`).

## Durability: Postgres, not a workflow engine

- Case state machine: 16 statuses, transitions only via
  `domain/state_machine.py:transition()`, which validates against an explicit
  table and writes an audit event in the same transaction.
- Waits (reply timeouts, follow-ups) are `scheduled_jobs` rows claimed by
  atomic compare-and-set updates.
- Sends go through the **transactional outbox** (`outbox_messages`) with a
  unique idempotency key per agent action. Crash recovery asks the provider
  whether the key already went out before retrying — never blind-resends.
- The worker (`workflows/worker.py`) is stateless; kill it anywhere and
  restart without duplicate sends (covered by tests).

If orchestration outgrows this, the activity/orchestration split maps
mechanically onto Temporal.

## Channels

`channels/base.py` defines `ChannelAdapter` (send / fetch_inbound /
find_by_idempotency_key). Every message in either direction on any channel is
a `communications` row tied to a `conversations` thread.

**Email is multi-provider by design** — never Gmail-only. Adapters are
selected per connected account (`connected_accounts.provider`) by
`channels/resolver.py`: `mock` (dev/simulator), `gmail` (Gmail REST API),
`outlook` (Microsoft Graph: Outlook.com/Hotmail/M365), and `imap_smtp`
(generic IMAP/SMTP with app passwords: Yahoo, iCloud, Fastmail, custom
domains — the long tail). All implemented against injectable transports and
covered by fakes in `tests/channels/`. Adding a provider must never touch
the agent, policy, or workflow layers.

Cross-provider exactly-once: every outbound email carries a deterministic
`Message-ID` derived from its outbox idempotency key
(`channels/mime_utils.py`), searchable on every provider (Gmail
`rfc822msgid:`, Graph `internetMessageId eq`, IMAP `HEADER Message-ID` on the
Sent folder, which the IMAP adapter populates via APPEND). Crash recovery
asks the provider before ever resending. Threading uses native thread ids
where they exist (Gmail threadId, Graph conversationId) and RFC-2822
`References`-root threading for IMAP.

OAuth (Gmail/Outlook) lives in `channels/oauth.py` + `/connect` endpoints;
refresh tokens are Fernet-encrypted at rest (`security/crypto.py`; dev mode
derives a local key, production requires `KARENBOT_TOKEN_ENCRYPTION_KEY`).
Revoking a connected account drops its ciphertext immediately. Note: the
OAuth `state` is a dev stub pending Clerk sessions (CSRF nonce required
before production). Also planned: `VoiceAdapter` (post-MVP; a call becomes a
transcript in the same tables).

Inbound mail that cannot be matched to a known thread is routed to human
review (`inbound.unmatched` audit event) — never guessed onto a case.

## LLM layer

`llm/base.py` is a thin transport protocol; implementations:
`AnthropicClient` (Claude, structured output via forced tool use; Sonnet for
drafting, Haiku for classification) and `ScriptedClient` (deterministic,
powers tests and the demo with no API key). Prompts are versioned files in
`agent/prompts/<task>/v<N>.md`; every agent action records its prompt and
model version.

Prompt-injection defenses are architectural: inbound content is data inside a
JSON document, the reply interpreter has no tools and a constrained output
schema, recipients only resolve from the verified-channel table, and the
policy engine gates everything. See `tests/injection/`.

## Repository layout

See the project README. Key invariants:

1. No side effect without an `agent_actions` row and a policy verdict.
2. No case status change outside `transition()`.
3. No outbound message outside the outbox.
4. Append-only `audit_events` for everything.

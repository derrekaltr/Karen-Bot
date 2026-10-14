# KarenBot

**Stop fighting customer service. KarenBot does it for you.**

KarenBot is an autonomous AI consumer-recovery platform: connect your email,
tell Karen what happened, grant scoped authority, and an AI agent researches
the company's policies, contacts their verified support channel, negotiates
factually, follows up for weeks if needed, and records the verified outcome.

> Status: MVP in development. The full simulated end-to-end flow works
> locally with no external credentials. **No real companies are contacted,
> no money moves, and no customers are charged** until the safety, legal,
> and compliance gates in `docs/` are cleared. KarenBot is not a law firm
> and does not provide legal advice.

## Quick start

```bash
make install     # Python venv + npm workspaces
make test        # 32 tests: state machine, policy engine, outbox, injection, e2e
make demo-e2e    # watch a full case resolve against a simulated airline
make dev         # Postgres (+ optional MinIO) via docker compose
make migrate     # Alembic migrations
make api         # FastAPI on :8000
npm run dev:web  # Next.js on :3000
```

`make demo-e2e` runs the whole product loop in one process: case intake →
fact extraction → eligibility against a verified policy → customer
authorization → policy-checked outreach → simulated lowball reply → an
autonomous counter → full-amount offer → customer approval of the binding
acceptance → verified recovery → `RESOLVED`, with a printed audit trail. It
also kills and restarts the delivery worker mid-flow to prove no duplicate
emails are sent.

Set `KARENBOT_LLM_PROVIDER=anthropic` and `KARENBOT_ANTHROPIC_API_KEY=...` to
run the same flow with Claude instead of the deterministic scripted model.

## Layout

```
apps/web        Next.js 15 + Tailwind (landing, dashboard shell, intake UI)
apps/api        FastAPI + SQLAlchemy + Alembic
  src/karenbot/
    domain/     models, 16-state case machine, audit events
    policy/     deterministic policy engine (the safety core)
    agent/      ProposedAction contract, runtime, versioned prompts, eligibility
    channels/   ChannelAdapter protocol, mock email (Gmail in M4, chat/voice later)
    workflows/  transactional outbox, scheduler, executor, worker loop
    llm/        provider abstraction: Anthropic + scripted
    simulator/  company personas (lowball, stonewall, injection attacker, ...)
  tests/        unit / policy / workflows / injection / e2e
packages/contracts  generated API types (placeholder)
infra/          docker-compose: Postgres+pgvector, MinIO (profile: storage)
docs/           architecture, state machine
```

## Safety model (short version)

The LLM can only *propose* typed actions. A pure, deterministic policy engine
checks authorization, verified recipients, claim types, amount ceilings, rate
limits, and duplicates; binding settlements always require explicit customer
approval. Recipients resolve only from a verified support-channel table.
Every proposal, verdict, message, and state change is audit-logged. Inbound
email is untrusted data — see `tests/injection/`. Customers can revoke
authority at any time (kill switch); admins can block any case.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `KARENBOT_DATABASE_URL` | local Postgres | SQLAlchemy URL |
| `KARENBOT_LLM_PROVIDER` | `scripted` | `scripted` or `anthropic` |
| `KARENBOT_ANTHROPIC_API_KEY` | – | required for `anthropic` |
| `KARENBOT_AGENT_MODEL` | `claude-sonnet-5-5` | drafting/reasoning model |
| `KARENBOT_CLASSIFIER_MODEL` | `claude-haiku-4-5-20251001` | reply classification |
| `KARENBOT_MAX_OUTBOUND_PER_CASE_PER_DAY` | 3 | global rate limit |
| `KARENBOT_MIN_HOURS_BETWEEN_OUTBOUND` | 20 | pacing floor |

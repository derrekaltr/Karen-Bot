# Deploying KarenBot publicly — karencollects.com

Architecture: the Next.js web app deploys to **Vercel**; the FastAPI
backend + Postgres + worker need a real host — **Railway** (simplest) or
Render. Vercel cannot run the API (long-lived worker loop, Postgres).

## 0. Before anything is public (hardening checklist)

- [ ] Rotate the Google OAuth client secret (it passed through chat during
      setup) — Google Cloud Console → Credentials → reset secret.
- [ ] Rotate the Anthropic API key (same reason) — platform.claude.com.
- [ ] Generate a strong `KARENBOT_ADMIN_TOKEN` (the "dev-admin" default is
      refused outside dev mode, but set a real one).
- [ ] Set `KARENBOT_DEV_MODE=false` in production. This hard-disables the
      /dev seed router and the X-User-Email auth fallback.
- [ ] Create a **production** Clerk instance (Clerk dashboard → create
      production; new publishable + secret keys; add the prod domain).
- [ ] Google OAuth client: add the production API callback
      (`https://api.karencollects.com/connect/google/callback`) to authorized
      redirect URIs. App verification/CASA is still required before
      non-test users can connect Gmail.
- [ ] `KARENBOT_CORS_ORIGINS=https://karencollects.com,https://www.karencollects.com`
- [ ] Fernet encryption key (`KARENBOT_TOKEN_ENCRYPTION_KEY`): generate fresh
      for prod (`python -m karenbot.security.crypto`); never reuse the dev key.
- [ ] Legal gates from docs/legal-risk.md remain open until entity +
      attorney review — a public marketing site is fine; do not onboard
      strangers as customers yet. Keep `KARENBOT_LLM_PROVIDER` and email
      provider in mind: real outbound email to companies must stay
      restricted to the allowlisted test setup until launch.

## 1. API on Railway

1. railway.app → New project → Deploy from GitHub repo → pick this repo.
2. Service root directory: `apps/api` (it has the Dockerfile).
3. Add the Postgres plugin; Railway injects `DATABASE_URL` — set
   `KARENBOT_DATABASE_URL` to `${DATABASE_URL}` with the driver prefix
   `postgresql+psycopg://` (swap `postgresql://`).
4. Environment variables (Service → Variables):
   - `KARENBOT_DEV_MODE=false`
   - `KARENBOT_ADMIN_TOKEN=<strong random>`
   - `KARENBOT_CORS_ORIGINS=https://karencollects.com,https://www.karencollects.com`
   - `KARENBOT_CLERK_PUBLISHABLE_KEY` / `KARENBOT_CLERK_SECRET_KEY` (prod
     instance)
   - `KARENBOT_TOKEN_ENCRYPTION_KEY=<fresh Fernet key>`
   - `KARENBOT_ANTHROPIC_API_KEY` + `KARENBOT_LLM_PROVIDER=anthropic`
   - `KARENBOT_GOOGLE_CLIENT_ID` / `KARENBOT_GOOGLE_CLIENT_SECRET`
     (rotated) + `KARENBOT_OAUTH_REDIRECT_BASE=https://api.karencollects.com`
5. Custom domain: `api.karencollects.com` → CNAME per Railway's instructions.
6. The container runs `alembic upgrade head` on boot — migrations apply
   automatically.

## 1b. Worker on Railway (required for anything asynchronous)

The API container only serves HTTP. Everything that happens *later* —
outbox email delivery, follow-up timers, inbound mail polling, and **push
notifications to the iPhone app** — runs in the worker loop. Without a
worker service, none of it happens in production.

1. In the same Railway project: New → GitHub repo → same repo, root
   `apps/api` (same Dockerfile).
2. Settings → Deploy → Custom start command:
   `python -m karenbot.workflows.worker`
3. Variables: share the API service's variables (Railway "shared
   variables"), especially `KARENBOT_DATABASE_URL`. No public domain.
4. Run exactly one replica to start (claims are race-safe, but one is
   plenty).

Push-specific variables (API + worker):
- `KARENBOT_PUSH_PROVIDER=expo` (default; `log` disables real sends)
- `KARENBOT_EXPO_ACCESS_TOKEN` — only if "enhanced push security" is
  enabled for the Expo project.

## 2. Web on Vercel

1. vercel.com → Add New → Project → import the GitHub repo.
2. Root Directory: `apps/web` (Framework: Next.js, auto-detected).
3. Environment variables:
   - `NEXT_PUBLIC_API_URL=https://api.karencollects.com`
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<prod publishable key>`
   - `CLERK_SECRET_KEY=<prod secret key>`
4. Deploy, then Settings → Domains → add `karencollects.com` and `www.karencollects.com`;
   point the registrar's DNS at Vercel (A 76.76.21.21 / CNAME
   cname.vercel-dns.com — Vercel shows the exact records).

## 3. Clerk production

Clerk dashboard → the KarenBot app → "Create production instance" →
add `karencollects.com`. Copy the new keys into Vercel (publishable + secret) and
Railway (`KARENBOT_CLERK_*`). Clerk walks through the DNS records it
needs (CNAMEs for accounts/clerk subdomains).

## 4. Smoke test order

1. `https://api.karencollects.com/health` → `{"status":"ok", ...}`
2. Web loads, sign-up works (Clerk prod).
3. `/events` renders (public), `/dashboard` requires sign-in.
4. /dev/* returns 404s and X-User-Email is rejected (dev mode off).
5. Admin endpoints refuse the old "dev-admin" token.

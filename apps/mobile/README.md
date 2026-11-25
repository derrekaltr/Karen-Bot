# KarenBot for iPhone (Expo)

The customer app: sign in, see your cases, scan your inbox for money, and
walk a case from evidence → eligibility → authorization → contact →
offer approval → confirmed recovery. Admin (`/admin`) and ops (`/ops`)
stay web-only.

Expo SDK 58 · Expo Router · `@clerk/expo` · shared API client in
`packages/api-client` (the same code the web app uses).

## Run it on your iPhone (no Xcode needed)

```bash
# terminal 1 — the API (from the repo root)
make api-lan                   # FastAPI on :8000, reachable from your phone

# terminal 2 — the app
cd apps/mobile
npm install                    # or: make install-mobile
npx expo start                 # scan the QR code with the Camera app → Expo Go
```

With no Clerk key set, the app runs in **dev mode**: "Continue as demo
user" signs in as the seeded `dana@example.com` via the API's dev-mode
header. The app finds your laptop's API automatically (same LAN address
Metro serves from), so phone and laptop just need the same Wi-Fi.

To use real Clerk sign-in, copy `.env.example` to `.env.local` and set
`EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` (same Clerk instance as the web).

## Layout

```
src/app/                 routes (Expo Router)
  _layout.tsx            fonts, auth provider, signed-in/out guard
  sign-in.tsx            Clerk hosted sign-in / sign-up (or demo in dev)
  (app)/index.tsx        your cases: "Needs you" / "Karen's on it" / "Closed"
  (app)/scan.tsx         inbox scan sheet → one tap starts a case
  (app)/cases/[id].tsx   case detail: every customer step of the case flow
src/components/          Karen design system (ui.tsx) + case sections
src/lib/                 config (API URL, auth mode), auth, polling hooks
```

## Auth

Sign-in opens Clerk's hosted Account Portal in a secure in-app browser
(`useHostedAuth`), so every sign-in method enabled for the Clerk instance
works without custom screens. API requests carry the Clerk session JWT:
the exact token the API already verifies for the web, so the backend
needed no changes.

Clerk dashboard setup (once the Apple Developer account exists):
**Configure → Native applications → iOS**: add Team ID + bundle ID
`com.karencollects.app`, and enable the Native API.

> App Store rule 4.8: if the Account Portal offers Google sign-in, also
> enable **Sign in with Apple** in Clerk before submitting.

## Ship to TestFlight

```bash
npx eas-cli@latest login
npx eas-cli@latest init                       # links the EAS project (writes projectId)
npx eas-cli@latest env:create --name EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY \
  --value pk_live_... --environment production --visibility plaintext
npx eas-cli@latest build -p ios --profile production   # EAS handles certs/profiles
npx eas-cli@latest submit -p ios --latest              # → App Store Connect / TestFlight
```

`preview` builds install directly on registered devices (ad hoc).
Release builds default to `https://api.karencollects.com`; a release
build without a Clerk key refuses to sign in rather than falling back to
the dev header.

## Checks

```bash
npm run typecheck
npx expo-doctor
npx expo export --platform ios   # full JS bundle, catches resolution errors
```

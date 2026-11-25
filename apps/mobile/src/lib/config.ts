import Constants from "expo-constants";
import { configureApiClient } from "@karenbot/api-client";

const PRODUCTION_API_URL = "https://api.karencollects.com";

/**
 * Where the API lives.
 *
 * 1. EXPO_PUBLIC_API_URL wins when set.
 * 2. In development, use the dev machine's LAN address (the same host Metro
 *    is served from) on :8000, so a physical iPhone running Expo Go reaches
 *    `make api` on your laptop. `localhost` would point at the phone itself.
 * 3. Release builds default to production.
 */
function resolveApiUrl(): string {
  const explicit = process.env.EXPO_PUBLIC_API_URL;
  if (explicit) return explicit;
  if (__DEV__) {
    const host = Constants.expoConfig?.hostUri?.split(":")[0];
    return `http://${host ?? "localhost"}:8000`;
  }
  return PRODUCTION_API_URL;
}

export const API_URL = resolveApiUrl();

export const CLERK_PUBLISHABLE_KEY =
  process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

/**
 * "clerk": real sign-in. "dev": no Clerk key in a dev build — requests
 * authenticate as the seeded demo user via the API's dev-mode header.
 * "misconfigured": a release build without a Clerk key; never silently
 * fall back to the dev header against production.
 */
export const AUTH_MODE: "clerk" | "dev" | "misconfigured" =
  CLERK_PUBLISHABLE_KEY !== "" ? "clerk" : __DEV__ ? "dev" : "misconfigured";

configureApiClient({ baseUrl: API_URL });

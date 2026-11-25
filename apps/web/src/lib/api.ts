/**
 * Web entry point for the shared KarenBot API client.
 *
 * The client itself lives in packages/api-client so the mobile app uses the
 * exact same types and endpoints. This module configures it for the web
 * (NEXT_PUBLIC_API_URL is inlined at build time) and re-exports everything,
 * so `@/lib/api` imports keep working unchanged.
 */
import { configureApiClient } from "@karenbot/api-client";

configureApiClient({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

export * from "@karenbot/api-client";

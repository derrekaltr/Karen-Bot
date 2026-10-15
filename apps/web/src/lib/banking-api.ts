/**
 * Typed fetch client for the KarenBot banking/discovery API (`/banking/*`).
 *
 * Same dev-auth pattern as `api.ts`: every request carries `X-User-Email`.
 * In mock mode there is no real Plaid Link UI — the subscriptions page
 * exchanges the sentinel public token "mock-public-token" directly.
 */

import { ApiError, DEV_USER_EMAIL } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BankConnection {
  id: string;
  provider: string;
  institution_name: string | null;
  status: string;
  created_at: string;
}

export type SubscriptionCadence = "weekly" | "monthly" | "yearly";

export type SubscriptionStatus =
  | "detected"
  | "case_created"
  | "dismissed"
  | "canceled";

export type SubscriptionAction = "cancel" | "negotiate" | "refund" | "dismiss";

export interface Subscription {
  id: string;
  merchant_name: string;
  /** Pydantic serializes Decimal as a JSON string. */
  amount: string;
  currency: string;
  cadence: SubscriptionCadence;
  occurrences: number;
  last_seen: string | null;
  /** Pydantic serializes Decimal as a JSON string. */
  yearly_cost: string;
  status: SubscriptionStatus;
  case_id: string | null;
  company_targetable: boolean;
}

export interface SubscriptionActionResult {
  status: string;
  case_id?: string;
  contact_mode?: "agent" | "assist";
}

// ---------------------------------------------------------------------------
// Fetch plumbing (mirrors api.ts)
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  init?: { method?: "GET" | "POST"; body?: unknown },
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: init?.method ?? "GET",
    headers: {
      "X-User-Email": DEV_USER_EMAIL,
      ...(init?.body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload: unknown = await response.json();
      if (
        typeof payload === "object" &&
        payload !== null &&
        "detail" in payload
      ) {
        const d = (payload as { detail: unknown }).detail;
        detail = typeof d === "string" ? d : JSON.stringify(d);
      }
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export function createLinkToken(): Promise<{ link_token: string }> {
  return request("/banking/link-token", { method: "POST" });
}

export function exchangePublicToken(input: {
  public_token: string;
  institution_name?: string;
}): Promise<BankConnection> {
  return request("/banking/exchange", { method: "POST", body: input });
}

export function listConnections(): Promise<BankConnection[]> {
  return request("/banking/connections");
}

export function revokeConnection(
  connectionId: string,
): Promise<{ status: string }> {
  return request(`/banking/connections/${connectionId}/revoke`, {
    method: "POST",
  });
}

export function refreshSubscriptions(): Promise<Subscription[]> {
  return request("/banking/refresh", { method: "POST" });
}

export function listSubscriptions(): Promise<Subscription[]> {
  return request("/banking/subscriptions");
}

export function actOnSubscription(
  subscriptionId: string,
  action: SubscriptionAction,
): Promise<SubscriptionActionResult> {
  return request(`/banking/subscriptions/${subscriptionId}/action`, {
    method: "POST",
    body: { action },
  });
}

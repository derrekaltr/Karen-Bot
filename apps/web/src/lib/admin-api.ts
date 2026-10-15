/**
 * Typed fetch client for the KarenBot admin API.
 *
 * Every request carries `X-Admin-Token`. The token lives in localStorage
 * under {@link ADMIN_TOKEN_STORAGE_KEY} and is passed explicitly to each
 * call so components stay in control of 403 handling (clear + re-gate).
 */

import { ApiError, type CaseStatus } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const ADMIN_TOKEN_STORAGE_KEY = "kb_admin_token";

// ---------------------------------------------------------------------------
// Token storage (browser only)
// ---------------------------------------------------------------------------

export function getStoredAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
}

export function storeAdminToken(token: string): void {
  window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
}

export function clearAdminToken(): void {
  window.localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AdminCase {
  id: string;
  status: CaseStatus;
  category: string;
  company_name: string;
  user_email: string;
  /** Pydantic serializes Decimal as a JSON string. */
  requested_amount: string | null;
  created_at: string;
  updated_at: string;
}

export const INTERVENTION_KINDS = [
  "inbound.unmatched",
  "security.suspected_injection",
  "action_denied",
  "delivery_failed",
] as const;

export type InterventionKind = (typeof INTERVENTION_KINDS)[number];

export interface InterventionItem {
  kind: InterventionKind;
  case_id: string | null;
  detail: string;
  timestamp: string;
}

export interface AdminMetrics {
  cases_by_status: Partial<Record<CaseStatus, number>>;
  verified_recovered_total: number;
  actions_denied: number;
  injection_flags: number;
  outbox: Record<string, number>;
  total_communications: number;
  kill_switch_active: boolean;
}

// ---------------------------------------------------------------------------
// Fetch plumbing (same ApiError contract as lib/api.ts)
// ---------------------------------------------------------------------------

async function adminRequest<T>(
  token: string,
  path: string,
  init?: { method?: "GET" | "POST"; body?: unknown },
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: init?.method ?? "GET",
    headers: {
      "X-Admin-Token": token,
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

export function listAdminCases(
  token: string,
  status?: CaseStatus,
): Promise<AdminCase[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return adminRequest(token, `/admin/cases${query}`);
}

export function pauseCase(
  token: string,
  caseId: string,
): Promise<{ status: CaseStatus }> {
  return adminRequest(token, `/admin/cases/${caseId}/pause`, {
    method: "POST",
  });
}

export function resumeCase(
  token: string,
  caseId: string,
): Promise<{ status: CaseStatus }> {
  return adminRequest(token, `/admin/cases/${caseId}/resume`, {
    method: "POST",
  });
}

export function getKillSwitch(
  token: string,
): Promise<{ kill_switch_active: boolean }> {
  return adminRequest(token, "/admin/kill-switch");
}

export function setKillSwitch(
  token: string,
  active: boolean,
): Promise<{ kill_switch_active: boolean }> {
  return adminRequest(token, "/admin/kill-switch", {
    method: "POST",
    body: { active },
  });
}

export function getInterventionQueue(
  token: string,
): Promise<InterventionItem[]> {
  return adminRequest(token, "/admin/intervention-queue");
}

export function getAdminMetrics(token: string): Promise<AdminMetrics> {
  return adminRequest(token, "/admin/metrics");
}

// ---------------------------------------------------------------------------
// Support channels (verification workflow)
// ---------------------------------------------------------------------------

export interface AdminChannel {
  id: string;
  company_name: string;
  channel: string;
  address: string;
  purpose: string;
  is_escalation: boolean;
  verified: boolean;
  verification_source_url: string | null;
}

export function listChannels(
  token: string,
  verified?: boolean,
): Promise<AdminChannel[]> {
  const query = verified === undefined ? "" : `?verified=${verified}`;
  return adminRequest(token, `/admin/channels${query}`);
}

export function verifyChannel(
  token: string,
  channelId: string,
): Promise<{ verified: boolean; address: string }> {
  return adminRequest(token, `/admin/channels/${channelId}/verify`, {
    method: "POST",
  });
}

export function deactivateChannel(
  token: string,
  channelId: string,
): Promise<{ active: boolean }> {
  return adminRequest(token, `/admin/channels/${channelId}/deactivate`, {
    method: "POST",
  });
}

/**
 * Typed fetch client for the KarenBot FastAPI backend.
 *
 * Auth: when a Clerk session is active, requests carry its Bearer token
 * (register the getter via `setSessionTokenGetter` — see
 * components/ClerkTokenBridge). Without one, dev mode falls back to the
 * `X-User-Email` header. Call `seed()` once (e.g. on dashboard mount) to
 * create the demo user + companies.
 */

export const DEV_USER_EMAIL = "dana@example.com";

type SessionTokenGetter = () => Promise<string | null>;

let sessionTokenGetter: SessionTokenGetter | null = null;

/** Wired by ClerkTokenBridge inside the ClerkProvider tree. */
export function setSessionTokenGetter(getter: SessionTokenGetter | null): void {
  sessionTokenGetter = getter;
}

export async function authHeaders(): Promise<Record<string, string>> {
  if (sessionTokenGetter) {
    try {
      const token = await sessionTokenGetter();
      if (token) return { Authorization: `Bearer ${token}` };
    } catch {
      // fall through to the dev header
    }
  }
  return { "X-User-Email": DEV_USER_EMAIL };
}

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CaseStatus =
  | "DISCOVERED"
  | "AWAITING_INFORMATION"
  | "ELIGIBILITY_REVIEW"
  | "AWAITING_AUTHORIZATION"
  | "READY_TO_CONTACT"
  | "CONTACTING_COMPANY"
  | "AWAITING_RESPONSE"
  | "NEGOTIATING"
  | "ESCALATED"
  | "AWAITING_CUSTOMER_APPROVAL"
  | "OFFER_RECEIVED"
  | "VERIFYING_RECOVERY"
  | "RESOLVED"
  | "CLOSED_UNSUCCESSFUL"
  | "CANCELED"
  | "BLOCKED";

export const TERMINAL_STATUSES: ReadonlySet<CaseStatus> = new Set([
  "RESOLVED",
  "CLOSED_UNSUCCESSFUL",
  "CANCELED",
]);

export interface Company {
  id: string;
  name: string;
  industry: string;
  size_class: string;
  targetable: boolean;
  refuses_third_party: boolean;
  /** Claim types the agent can pursue (from verified policies); empty for assist-only companies. */
  claim_types: string[];
}

export interface CategoryOption {
  /** snake_case category key submitted to the API. */
  key: string;
  /** Human-readable display label. */
  label: string;
}

export interface CategoryCatalog {
  /** Categories always available in assist mode, regardless of company. */
  general: CategoryOption[];
  /** Industry-specific suggestions, keyed by industry (e.g. "airline"). */
  by_industry: Record<string, CategoryOption[]>;
  /** Industries a user can pick for an unknown company (includes "other"). */
  industries: string[];
}

export interface Case {
  id: string;
  status: CaseStatus;
  category: string;
  description: string;
  /** Pydantic serializes Decimal as a JSON string. */
  requested_amount: string | null;
  currency: string;
  company_name: string | null;
  /** "agent": Karen negotiates directly. "assist": Karen drafts, the customer sends. */
  contact_mode: "agent" | "assist";
  eligibility_basis: string | null;
  facts: Record<string, unknown>;
}

export interface CaseCreated {
  case: Case;
  karen_questions: string[];
}

export interface EligibilityResult {
  eligible: boolean;
  basis: string | null;
  reasons: string[];
  status: CaseStatus;
}

export interface AuthorizeResult {
  status: CaseStatus;
  loa_text: string;
}

export interface ContactResult {
  decision: "allow" | "deny" | "needs_approval";
  reasons: string[];
  status: CaseStatus;
}

export interface CommunicationClassification {
  draft_for_customer?: boolean;
  guidance?: string;
  [key: string]: unknown;
}

export interface Communication {
  id: string;
  channel: string;
  direction: "inbound" | "outbound";
  counterparty: "company" | "customer";
  subject: string | null;
  body: string;
  sent_at: string | null;
  received_at: string | null;
  created_at: string;
  classification: CommunicationClassification;
}

export interface AuditEvent {
  actor_type: string;
  event_type: string;
  event_payload: Record<string, unknown>;
  timestamp: string;
}

export interface Approval {
  id: string;
  action_type: string;
  proposed_action: Record<string, unknown>;
  policy_reasons: string[];
}

export interface TickResult {
  work_done: number;
  emails_sent_total: number;
  persona: string;
}

export const PERSONAS = [
  "lowball_then_accept",
  "immediate_refund",
  "stonewall",
  "asks_for_evidence",
  "customer_only",
  "prompt_injector",
] as const;

export type Persona = (typeof PERSONAS)[number];

// ---------------------------------------------------------------------------
// Fetch plumbing
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  /** FastAPI error `detail` string (e.g. the moral-code rejection). */
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  init?: { method?: "GET" | "POST"; body?: unknown },
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: init?.method ?? "GET",
    headers: {
      ...(await authHeaders()),
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

export function seed(): Promise<{ user_email: string; companies: string[] }> {
  return request("/dev/seed", { method: "POST", body: {} });
}

export function listCompanies(): Promise<Company[]> {
  return request("/companies");
}

/** Full category catalog: general options plus industry-specific ones. */
export function getCategoryCatalog(): Promise<CategoryCatalog> {
  return request("/categories");
}

export function createCase(input: {
  company_name: string;
  category: string;
  description: string;
  requested_amount: number | null;
  /** For unknown companies: what kind of business it is. */
  company_industry?: string;
}): Promise<CaseCreated> {
  return request("/cases", { method: "POST", body: input });
}

export function listCases(): Promise<Case[]> {
  return request("/cases");
}

export function getCase(caseId: string): Promise<Case> {
  return request(`/cases/${caseId}`);
}

export function addEvidence(
  caseId: string,
  input: { evidence_type: string; summary: string },
): Promise<Case> {
  return request(`/cases/${caseId}/evidence`, { method: "POST", body: input });
}

export function completeIntake(caseId: string): Promise<EligibilityResult> {
  return request(`/cases/${caseId}/intake/complete`, { method: "POST" });
}

export function authorizeCase(
  caseId: string,
  signedName: string,
): Promise<AuthorizeResult> {
  return request(`/cases/${caseId}/authorize`, {
    method: "POST",
    body: { signed_name: signedName },
  });
}

export function initiateContact(caseId: string): Promise<ContactResult> {
  return request(`/cases/${caseId}/contact`, { method: "POST" });
}

export function listCommunications(caseId: string): Promise<Communication[]> {
  return request(`/cases/${caseId}/communications`);
}

export function listAudit(caseId: string): Promise<AuditEvent[]> {
  return request(`/cases/${caseId}/audit`);
}

export function listApprovals(caseId: string): Promise<Approval[]> {
  return request(`/cases/${caseId}/approvals`);
}

export function approveAction(
  actionId: string,
): Promise<{ status: CaseStatus }> {
  return request(`/approvals/${actionId}/approve`, { method: "POST" });
}

export function confirmRecovery(
  caseId: string,
): Promise<{ status: CaseStatus }> {
  return request(`/cases/${caseId}/confirm-recovery`, { method: "POST" });
}

export function revokeCase(caseId: string): Promise<{ status: CaseStatus }> {
  return request(`/cases/${caseId}/revoke`, { method: "POST" });
}

export function devTick(input: {
  persona?: Persona;
  ticks?: number;
}): Promise<TickResult> {
  return request("/dev/tick", { method: "POST", body: input });
}

// ---------------------------------------------------------------------------
// Presentation helpers
// ---------------------------------------------------------------------------

/** "baggage_delay_expenses" -> "Baggage delay expenses" */
export function humanize(value: string): string {
  const spaced = value.replace(/_/g, " ").toLowerCase();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function formatAmount(
  amount: string | null,
  currency: string,
): string | null {
  if (amount === null || amount === "") return null;
  const numeric = Number(amount);
  if (Number.isNaN(numeric)) return `${amount} ${currency}`;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
  }).format(numeric);
}

export type StatusTone = "green" | "amber" | "red" | "neutral";

export function statusTone(status: CaseStatus): StatusTone {
  if (status === "RESOLVED") return "green";
  if (status.startsWith("AWAITING_")) return "amber";
  if (
    status === "CANCELED" ||
    status === "CLOSED_UNSUCCESSFUL" ||
    status === "BLOCKED"
  ) {
    return "red";
  }
  return "neutral";
}

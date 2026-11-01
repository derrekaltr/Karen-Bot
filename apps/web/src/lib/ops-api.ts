/** Typed client for the Ops Council API (/ops). Same auth as lib/api. */

import { ApiError, authHeaders } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const ITEM_KINDS = [
  "design_concept",
  "proposal",
  "task",
  "decision",
] as const;

export type ItemKind = (typeof ITEM_KINDS)[number] | "research_brief";

export const KIND_LABELS: Record<ItemKind, string> = {
  design_concept: "Design concept",
  proposal: "Proposal",
  task: "Task",
  decision: "Decision",
  research_brief: "Research",
};

export type ItemStatus =
  | "new"
  | "in_review"
  | "approved"
  | "changes_requested"
  | "archived";

export interface OpsMember {
  id: string;
  email: string;
  display_name: string;
  role: "owner" | "member";
}

export interface OpsItem {
  id: string;
  kind: ItemKind;
  title: string;
  body: string;
  status: ItemStatus;
  created_by_email: string;
  reviewer_email: string | null;
  recommendation: string | null;
  source_urls: string[];
  decided_at: string | null;
  created_at: string;
  comment_count: number;
}

export interface OpsComment {
  id: string;
  author_email: string;
  body: string;
  created_at: string;
}

export interface OpsItemDetail extends OpsItem {
  comments: OpsComment[];
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

export function getMe(): Promise<OpsMember> {
  return request("/ops/me");
}

export function listMembers(): Promise<OpsMember[]> {
  return request("/ops/members");
}

export function addMember(input: {
  email: string;
  display_name: string;
  role?: "owner" | "member";
}): Promise<OpsMember> {
  return request("/ops/members", { method: "POST", body: input });
}

export type ItemBox = "all" | "inbox" | "sent" | "research" | "decisions";

export interface OpsMetrics {
  total_cases: number;
  resolved_cases: number;
  recovered_total: number;
  yearly_savings: number;
}

export function getOpsMetrics(): Promise<OpsMetrics> {
  return request("/ops/metrics");
}

export function listItems(box: ItemBox = "all"): Promise<OpsItem[]> {
  return request(`/ops/items?box=${box}`);
}

export function createItem(input: {
  kind: ItemKind;
  title: string;
  body: string;
  reviewer_email: string | null;
}): Promise<OpsItem> {
  return request("/ops/items", { method: "POST", body: input });
}

export function getItem(itemId: string): Promise<OpsItemDetail> {
  return request(`/ops/items/${itemId}`);
}

export function addComment(
  itemId: string,
  body: string,
): Promise<OpsComment> {
  return request(`/ops/items/${itemId}/comments`, {
    method: "POST",
    body: { body },
  });
}

export function approveItem(
  itemId: string,
  comment: string | null,
): Promise<OpsItem> {
  return request(`/ops/items/${itemId}/approve`, {
    method: "POST",
    body: { comment },
  });
}

export function requestChanges(
  itemId: string,
  comment: string | null,
): Promise<OpsItem> {
  return request(`/ops/items/${itemId}/request-changes`, {
    method: "POST",
    body: { comment },
  });
}

export function resubmitItem(itemId: string): Promise<OpsItem> {
  return request(`/ops/items/${itemId}/resubmit`, { method: "POST" });
}

export function runResearch(): Promise<{ proposed: number; created: number }> {
  return request("/ops/research/run", { method: "POST" });
}

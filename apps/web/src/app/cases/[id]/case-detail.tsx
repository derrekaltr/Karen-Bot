"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import {
  ApiError,
  PERSONAS,
  TERMINAL_STATUSES,
  approveAction,
  authorizeCase,
  confirmRecovery,
  devTick,
  formatAmount,
  getCase,
  humanize,
  initiateContact,
  listApprovals,
  listAudit,
  listCommunications,
  revokeCase,
  scanCaseEvidence,
  type Approval,
  type AuditEvent,
  type Case,
  type Communication,
  type Persona,
  type ScanEvidence,
} from "@/lib/api";

const EVIDENCE_COLLAPSE_COUNT = 3;

const POLL_INTERVAL_MS = 3000;
const BODY_TRUNCATE_LENGTH = 400;

interface CaseData {
  caseRecord: Case;
  communications: Communication[];
  approvals: Approval[];
  audit: AuditEvent[];
}

export function CaseDetail({ caseId }: { caseId: string }) {
  const [data, setData] = useState<CaseData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [persona, setPersona] = useState<Persona>("lowball_then_accept");
  const [expandedBodies, setExpandedBodies] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [signedName, setSignedName] = useState("");
  const [loaText, setLoaText] = useState<string | null>(null);
  const [evidenceScanning, setEvidenceScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanEvidence[] | null>(null);
  const [showAllEvidence, setShowAllEvidence] = useState(false);

  const refetch = useCallback(async () => {
    try {
      const [caseRecord, communications, approvals, audit] = await Promise.all(
        [
          getCase(caseId),
          listCommunications(caseId),
          listApprovals(caseId),
          listAudit(caseId),
        ],
      );
      setData({ caseRecord, communications, approvals, audit });
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach the KarenBot API.",
      );
    }
  }, [caseId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const status = data?.caseRecord.status;
  const isTerminal = status !== undefined && TERMINAL_STATUSES.has(status);

  useEffect(() => {
    if (status === undefined || isTerminal) return;
    const timer = setInterval(() => {
      void refetch();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [status, isTerminal, refetch]);

  async function runAction(action: () => Promise<unknown>) {
    setActionError(null);
    setBusy(true);
    try {
      await action();
      await refetch();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Action failed — try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  function toggleExpanded(id: string) {
    setExpandedBodies((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function submitAuthorization() {
    if (signedName.trim() === "") {
      setActionError("Type your full name to sign.");
      return;
    }
    const name = signedName.trim();
    await runAction(async () => {
      const result = await authorizeCase(caseId, name);
      setLoaText(result.loa_text);
    });
  }

  async function sendKaren() {
    await runAction(async () => {
      const result = await initiateContact(caseId);
      if (result.decision === "deny") {
        throw new ApiError(
          422,
          `Karen can't make contact yet: ${result.reasons.join("; ")}`,
        );
      }
    });
  }

  async function scanForEvidence() {
    setEvidenceScanning(true);
    try {
      await runAction(async () => {
        const result = await scanCaseEvidence(caseId);
        setScanResult(result);
        setShowAllEvidence(false);
      });
    } finally {
      setEvidenceScanning(false);
    }
  }

  async function copyBody(comm: Communication) {
    try {
      await navigator.clipboard.writeText(comm.body);
      setCopiedId(comm.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      setActionError("Could not copy to clipboard.");
    }
  }

  if (error !== null && data === null) {
    return (
      <Card className="border-red-200 bg-red-50">
        <p className="text-sm font-medium text-red-700">
          Could not load this case: {error}
        </p>
      </Card>
    );
  }

  if (data === null) {
    return <p className="text-sm text-ink-400">Loading case…</p>;
  }

  const { caseRecord, communications, approvals, audit } = data;
  const amount = formatAmount(
    caseRecord.requested_amount,
    caseRecord.currency,
  );
  const companyLabel = caseRecord.company_name ?? "the company";

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              {companyLabel}
            </h1>
            <p className="mt-1 text-sm text-ink-600">
              {humanize(caseRecord.category)}
              {amount !== null ? ` · ${amount}` : ""}
            </p>
            {caseRecord.eligibility_basis !== null && (
              <p className="mt-2 inline-block rounded-md bg-accent-50 px-2.5 py-1 text-xs font-medium text-accent-700">
                Eligibility basis: {caseRecord.eligibility_basis}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={caseRecord.status} />
            {caseRecord.contact_mode === "assist" && (
              <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-ink-600">
                Assist mode
              </span>
            )}
          </div>
        </div>
        {error !== null && (
          <p className="mt-3 text-xs text-amber-700">
            Live updates interrupted: {error}
          </p>
        )}
      </Card>

      {actionError !== null && (
        <p
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
        >
          {actionError}
        </p>
      )}

      {/* Authorization */}
      {caseRecord.status === "AWAITING_AUTHORIZATION" && (
        <Card className="border-accent-500/50 bg-accent-50/60">
          <h2 className="text-base font-semibold">
            Karen needs your authorization
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-600">
            Before Karen can go after {companyLabel} on your behalf, you need
            to sign a Letter of Authorization. Type your full legal name below
            to sign — you can revoke it at any time.
          </p>
          <form
            className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              void submitAuthorization();
            }}
          >
            <div className="flex flex-1 flex-col gap-1.5">
              <label htmlFor="signed-name" className="text-sm font-medium">
                Type your full name to sign
              </label>
              <input
                id="signed-name"
                type="text"
                placeholder="e.g. Dana Example"
                value={signedName}
                onChange={(event) => setSignedName(event.target.value)}
                className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm focus:border-accent-600"
              />
            </div>
            <Button type="submit" disabled={busy}>
              {busy ? "Signing…" : "Authorize KarenBot"}
            </Button>
          </form>
        </Card>
      )}

      {loaText !== null && (
        <details className="rounded-xl border border-slate-200 bg-slate-50">
          <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">
            Your signed Letter of Authorization
          </summary>
          <pre className="max-h-64 overflow-y-auto border-t border-slate-200 px-4 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
            {loaText}
          </pre>
        </details>
      )}

      {/* Ready to contact */}
      {caseRecord.status === "READY_TO_CONTACT" && (
        <Card className="border-accent-500/50 bg-accent-50/60">
          <h2 className="text-base font-semibold">Karen is ready</h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-600">
            Authorization signed. Say the word and Karen makes first contact
            with {companyLabel}.
          </p>
          <div className="mt-4">
            <Button disabled={busy} onClick={() => void sendKaren()}>
              {busy
                ? "Dispatching…"
                : caseRecord.contact_mode === "assist"
                  ? "Have Karen draft it"
                  : "Send Karen after them"}
            </Button>
          </div>
        </Card>
      )}

      {/* Approvals */}
      {approvals.length > 0 && (
        <Card className="border-amber-300 bg-amber-50">
          <h2 className="text-base font-semibold text-amber-900">
            Karen needs your approval
          </h2>
          <ul className="mt-3 flex flex-col gap-4">
            {approvals.map((approval) => (
              <li
                key={approval.id}
                className="rounded-lg border border-amber-200 bg-white p-4"
              >
                <p className="text-sm font-semibold">
                  {humanize(approval.action_type)}
                </p>
                <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                  {Object.entries(approval.proposed_action).map(
                    ([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <dt className="font-medium text-ink-600">
                          {humanize(key)}:
                        </dt>
                        <dd className="break-all">
                          {typeof value === "object"
                            ? JSON.stringify(value)
                            : String(value)}
                        </dd>
                      </div>
                    ),
                  )}
                </dl>
                {approval.policy_reasons.length > 0 && (
                  <p className="mt-2 text-xs text-ink-600">
                    Why approval is needed:{" "}
                    {approval.policy_reasons.join("; ")}
                  </p>
                )}
                <div className="mt-3">
                  <Button
                    disabled={busy}
                    onClick={() =>
                      void runAction(() => approveAction(approval.id))
                    }
                  >
                    Approve
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Timeline */}
      <Card className="p-0">
        <h2 className="border-b border-slate-200 px-6 py-4 text-base font-semibold">
          Timeline
        </h2>
        {communications.length === 0 ? (
          <p className="px-6 py-8 text-sm text-ink-400">
            No messages yet — Karen hasn&apos;t made contact.
          </p>
        ) : (
          <ul className="flex flex-col gap-4 p-6">
            {communications.map((comm) => {
              const isDraftForCustomer =
                comm.classification.draft_for_customer === true;
              const isOutboundToCompany =
                comm.direction === "outbound" &&
                comm.counterparty === "company" &&
                !isDraftForCustomer;
              const expanded = expandedBodies.has(comm.id);
              const needsTruncation =
                comm.body.length > BODY_TRUNCATE_LENGTH && !expanded;
              const bodyText = needsTruncation
                ? `${comm.body.slice(0, BODY_TRUNCATE_LENGTH)}…`
                : comm.body;
              const timestamp =
                comm.sent_at ?? comm.received_at ?? comm.created_at;

              if (isDraftForCustomer) {
                return (
                  <li key={comm.id}>
                    <div className="rounded-xl border-2 border-accent-500/50 bg-accent-50 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-accent-700">
                          Draft for you to send
                        </p>
                        <button
                          type="button"
                          onClick={() => void copyBody(comm)}
                          className="min-h-11 rounded-lg border border-accent-600 px-4 text-sm font-semibold text-accent-700 hover:bg-accent-100"
                        >
                          {copiedId === comm.id ? "Copied!" : "Copy"}
                        </button>
                      </div>
                      {typeof comm.classification.guidance === "string" && (
                        <p className="mt-1 text-sm text-ink-600">
                          {comm.classification.guidance}
                        </p>
                      )}
                      {comm.subject !== null && comm.subject !== "" && (
                        <p className="mt-3 text-sm font-bold">
                          {comm.subject}
                        </p>
                      )}
                      <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap">
                        {bodyText}
                      </p>
                      {comm.body.length > BODY_TRUNCATE_LENGTH && (
                        <button
                          type="button"
                          onClick={() => toggleExpanded(comm.id)}
                          className="mt-2 text-sm font-semibold text-accent-600 hover:text-accent-700"
                        >
                          {expanded ? "Show less" : "Show more"}
                        </button>
                      )}
                    </div>
                  </li>
                );
              }

              return (
                <li
                  key={comm.id}
                  className={`flex flex-col ${
                    isOutboundToCompany ? "items-end" : "items-start"
                  }`}
                >
                  <span className="mb-1 text-xs font-medium text-ink-400">
                    {isOutboundToCompany
                      ? `Karen → ${companyLabel}`
                      : comm.direction === "inbound"
                        ? companyLabel
                        : `Karen → you`}
                    {" · "}
                    {new Date(timestamp).toLocaleString()}
                  </span>
                  <div
                    className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                      isOutboundToCompany
                        ? "bg-accent-600 text-white"
                        : "bg-slate-100 text-ink-900"
                    }`}
                  >
                    {comm.subject !== null && comm.subject !== "" && (
                      <p className="font-bold">{comm.subject}</p>
                    )}
                    <p className="mt-1 whitespace-pre-wrap">{bodyText}</p>
                    {comm.body.length > BODY_TRUNCATE_LENGTH && (
                      <button
                        type="button"
                        onClick={() => toggleExpanded(comm.id)}
                        className={`mt-2 text-sm font-semibold underline ${
                          isOutboundToCompany
                            ? "text-white/90"
                            : "text-accent-600"
                        }`}
                      >
                        {expanded ? "Show less" : "Show more"}
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {/* Action bar */}
      <div className="flex flex-wrap items-center gap-3">
        {caseRecord.status === "VERIFYING_RECOVERY" && (
          <Button
            disabled={busy}
            onClick={() => void runAction(() => confirmRecovery(caseId))}
          >
            I received the money
          </Button>
        )}
        {!isTerminal && (
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => void scanForEvidence()}
          >
            {evidenceScanning
              ? "Scanning your inbox…"
              : "Scan inbox for evidence"}
          </Button>
        )}
        {!isTerminal && (
          <Button
            variant="danger"
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  "Stop Karen and revoke her authorization? She will cease all contact with the company.",
                )
              ) {
                void runAction(() => revokeCase(caseId));
              }
            }}
          >
            Stop Karen / revoke authorization
          </Button>
        )}
      </div>

      {/* Inbox evidence scan result */}
      {scanResult !== null && (
        <Card>
          {scanResult.length === 0 ? (
            <p className="text-sm text-ink-600">
              No new matching emails found.
            </p>
          ) : (
            <>
              <h2 className="text-sm font-semibold">Evidence attached:</h2>
              <ul className="mt-2 flex flex-col gap-2">
                {(showAllEvidence
                  ? scanResult
                  : scanResult.slice(0, EVIDENCE_COLLAPSE_COUNT)
                ).map((evidence) => (
                  <li
                    key={evidence.id}
                    className="rounded-lg bg-slate-50 px-3 py-2 text-sm leading-relaxed text-ink-900"
                  >
                    {evidence.summary}
                  </li>
                ))}
              </ul>
              {scanResult.length > EVIDENCE_COLLAPSE_COUNT &&
                !showAllEvidence && (
                  <button
                    type="button"
                    onClick={() => setShowAllEvidence(true)}
                    className="mt-2 text-sm font-semibold text-accent-600 hover:text-accent-700"
                  >
                    Show all {scanResult.length}
                  </button>
                )}
            </>
          )}
        </Card>
      )}

      {/* Dev simulator */}
      <div className="rounded-xl border border-dashed border-slate-300 p-5">
        <p className="text-xs font-bold tracking-wide text-ink-400 uppercase">
          Simulator — dev only
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="persona" className="text-sm font-medium">
              Company persona
            </label>
            <select
              id="persona"
              value={persona}
              onChange={(event) =>
                setPersona(event.target.value as Persona)
              }
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
            >
              {PERSONAS.map((p) => (
                <option key={p} value={p}>
                  {humanize(p)}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() =>
              void runAction(() => devTick({ persona, ticks: 1 }))
            }
          >
            Simulate company response
          </Button>
        </div>
      </div>

      {/* Audit trail */}
      <details className="rounded-xl border border-slate-200">
        <summary className="cursor-pointer px-5 py-4 text-sm font-semibold">
          Audit trail ({audit.length})
        </summary>
        <ul className="border-t border-slate-200 px-5 py-4">
          {audit.map((event, index) => (
            <li
              key={index}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-slate-100 py-2 text-sm last:border-b-0"
            >
              <span className="font-mono text-xs text-ink-400">
                {new Date(event.timestamp).toLocaleString()}
              </span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-ink-600">
                {event.actor_type}
              </span>
              <span className="font-medium">{event.event_type}</span>
            </li>
          ))}
          {audit.length === 0 && (
            <li className="py-2 text-sm text-ink-400">No events yet.</li>
          )}
        </ul>
      </details>
    </div>
  );
}

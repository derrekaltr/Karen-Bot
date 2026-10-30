"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import {
  ApiError,
  TERMINAL_STATUSES,
  formatAmount,
  humanize,
  type CaseStatus,
} from "@/lib/api";
import {
  clearAdminToken,
  getAdminMetrics,
  getInterventionQueue,
  getKillSwitch,
  getStoredAdminToken,
  listAdminCases,
  deactivateChannel,
  listChannels,
  listAdminEvents,
  pauseCase,
  publishEvent,
  rejectEvent,
  resumeCase,
  runEventResearch,
  setKillSwitch,
  storeAdminToken,
  verifyChannel,
  type AdminCase,
  type AdminChannel,
  type AdminClaimEvent,
  type AdminMetrics,
  type InterventionItem,
  type InterventionKind,
} from "@/lib/admin-api";

const POLL_INTERVAL_MS = 5_000;
const DETAIL_TRUNCATE_AT = 120;

const RED_KINDS: ReadonlySet<InterventionKind> = new Set([
  "security.suspected_injection",
  "delivery_failed",
]);

function isPausable(status: CaseStatus): boolean {
  return status !== "BLOCKED" && !TERMINAL_STATUSES.has(status);
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

// ---------------------------------------------------------------------------
// Token gate
// ---------------------------------------------------------------------------

function TokenGate({
  error,
  onSubmit,
}: {
  error: string | null;
  onSubmit: (token: string) => void;
}) {
  const [value, setValue] = useState("");

  return (
    <div className="flex min-h-dvh items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-sm">
        <h1 className="text-lg font-semibold tracking-tight">Admin console</h1>
        <p className="mt-1 text-sm text-ink-600">
          Enter the admin token to continue.
        </p>
        {error !== null && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
            {error}
          </p>
        )}
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            const trimmed = value.trim();
            if (trimmed !== "") onSubmit(trimmed);
          }}
        >
          <label className="block">
            <span className="sr-only">Admin token</span>
            <input
              type="password"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="dev token is dev-admin"
              autoFocus
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-accent-600 focus:ring-2 focus:ring-accent-600/20"
            />
          </label>
          <Button type="submit" className="w-full" disabled={value.trim() === ""}>
            Enter admin console
          </Button>
        </form>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-medium tracking-wide text-ink-600 uppercase">
        {label}
      </p>
      <p className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</p>
    </Card>
  );
}

function MetricsSection({ metrics }: { metrics: AdminMetrics }) {
  const recovered = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(metrics.verified_recovered_total);
  const outboxPending = metrics.outbox["PENDING"] ?? 0;
  const outboxFailed = metrics.outbox["FAILED"] ?? 0;
  const byStatus = Object.entries(metrics.cases_by_status) as [
    CaseStatus,
    number,
  ][];

  return (
    <section aria-label="Metrics">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Verified recovered" value={recovered} />
        <MetricCard
          label="Communications"
          value={String(metrics.total_communications)}
        />
        <MetricCard
          label="Actions denied"
          value={String(metrics.actions_denied)}
        />
        <MetricCard
          label="Injection flags"
          value={String(metrics.injection_flags)}
        />
        <MetricCard
          label="Outbox pending / failed"
          value={`${outboxPending} / ${outboxFailed}`}
        />
      </div>
      {byStatus.length > 0 && (
        <Card className="mt-4 p-5">
          <p className="text-xs font-medium tracking-wide text-ink-600 uppercase">
            Cases by status
          </p>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
            {byStatus.map(([status, count]) => (
              <li key={status} className="flex items-center gap-1.5">
                <StatusBadge status={status} />
                <span className="text-sm font-semibold text-ink-900">
                  {count}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Support channels (verification workflow)
// ---------------------------------------------------------------------------

function ChannelsSection({
  channels,
  busyChannelId,
  onVerify,
  onDeactivate,
}: {
  channels: AdminChannel[];
  busyChannelId: string | null;
  onVerify: (id: string) => void;
  onDeactivate: (id: string) => void;
}) {
  const unverified = channels.filter((c) => !c.verified);
  const verified = channels.filter((c) => c.verified);
  return (
    <section aria-label="Support channels">
      <h2 className="text-base font-semibold">
        Support channels — verification queue ({unverified.length} pending)
      </h2>
      <p className="mt-1 text-sm text-ink-600">
        Karen can only send to verified channels. Open each source link,
        confirm the address matches, then verify. Verifications are audited.
      </p>
      <ul className="mt-3 flex flex-col gap-3">
        {unverified.map((channel) => (
          <li key={channel.id}>
            <Card className="border-amber-300/60">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold">
                    {channel.company_name}
                    <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-ink-600">
                      {channel.channel}
                    </span>
                    {channel.is_escalation && (
                      <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                        escalation
                      </span>
                    )}
                  </p>
                  <p className="mt-1 break-all font-mono text-sm text-ink-900">
                    {channel.address}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-600">{channel.purpose}</p>
                  {channel.verification_source_url && (
                    <a
                      href={channel.verification_source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-block text-xs font-semibold text-accent-600 hover:text-accent-700"
                    >
                      Open source to verify ↗
                    </a>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    disabled={busyChannelId === channel.id}
                    onClick={() => onVerify(channel.id)}
                  >
                    Verify
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={busyChannelId === channel.id}
                    onClick={() => onDeactivate(channel.id)}
                  >
                    Reject
                  </Button>
                </div>
              </div>
            </Card>
          </li>
        ))}
      </ul>
      {unverified.length === 0 && (
        <p className="mt-3 text-sm text-ink-400">
          No channels awaiting verification.
        </p>
      )}
      {verified.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold text-ink-600">
            Verified channels ({verified.length})
          </summary>
          <ul className="mt-2 flex flex-col gap-1">
            {verified.map((channel) => (
              <li
                key={channel.id}
                className="rounded-lg bg-slate-50 px-3 py-2 text-sm"
              >
                <span className="font-semibold">{channel.company_name}</span>{" "}
                <span className="font-mono">{channel.address}</span>
                <span className="ml-2 text-xs text-ink-400">
                  {channel.channel}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Intervention queue
// ---------------------------------------------------------------------------

function EventsSection({
  events,
  busyEventId,
  researching,
  researchResult,
  onPublish,
  onReject,
  onResearch,
}: {
  events: AdminClaimEvent[];
  busyEventId: string | null;
  researching: boolean;
  researchResult: string | null;
  onPublish: (id: string) => void;
  onReject: (id: string) => void;
  onResearch: () => void;
}) {
  return (
    <section aria-label="Claimable events">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight">
          Claimable events — drafts awaiting review ({events.length})
        </h2>
        <Button
          variant="secondary"
          disabled={researching}
          onClick={onResearch}
          className="min-h-9 px-4 py-2 text-xs"
        >
          {researching ? "Karen is researching…" : "Research now"}
        </Button>
      </div>
      {researchResult !== null && (
        <p className="mt-2 text-xs text-ink-600">{researchResult}</p>
      )}
      {events.length === 0 ? (
        <p className="mt-3 text-sm text-ink-400">
          No drafts waiting. Run research to look for new public events.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-4">
          {events.map((event) => (
            <li key={event.id}>
              <Card>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-bold">
                    {event.company_name}
                  </span>
                  <span className="text-xs text-ink-400">
                    {event.event_date}
                    {event.region !== null ? ` — ${event.region}` : ""}
                  </span>
                  <span className="rounded-full border-[1.5px] border-black bg-face-100 px-2 py-0.5 text-xs font-bold text-ink-600">
                    {humanize(event.category)}
                  </span>
                </div>
                <h3 className="mt-1 text-base font-bold">{event.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-600">
                  {event.summary}
                </p>
                <p className="mt-1 text-sm font-bold text-money-700">
                  {event.entitlement}
                </p>
                <p className="mt-1 text-xs text-ink-600">
                  Qualifies: {event.eligibility} — Claim: {event.how_to_claim}
                </p>
                {event.research_notes !== null && (
                  <p className="mt-1 text-xs text-ink-400">
                    Researcher notes: {event.research_notes}
                  </p>
                )}
                <ul className="mt-2 flex flex-col gap-0.5">
                  {event.source_urls.map((url) => (
                    <li key={url}>
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs break-all text-accent-600 underline"
                      >
                        {url}
                      </a>
                    </li>
                  ))}
                </ul>
                <div className="mt-3 flex gap-3">
                  <Button
                    disabled={busyEventId !== null}
                    onClick={() => onPublish(event.id)}
                  >
                    Publish
                  </Button>
                  <Button
                    variant="danger"
                    disabled={busyEventId !== null}
                    onClick={() => onReject(event.id)}
                  >
                    Reject
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


function KindBadge({ kind }: { kind: InterventionKind }) {
  const tone = RED_KINDS.has(kind)
    ? "bg-red-100 text-red-700"
    : "bg-amber-100 text-amber-800";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold whitespace-nowrap ${tone}`}
    >
      {kind}
    </span>
  );
}

function InterventionQueueSection({ items }: { items: InterventionItem[] }) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <section aria-label="Intervention queue">
      <h2 className="text-base font-semibold tracking-tight">
        Intervention queue
      </h2>
      {items.length === 0 ? (
        <Card className="mt-3 p-5">
          <p className="text-sm text-ink-600">
            Nothing needs human attention right now.
          </p>
        </Card>
      ) : (
        <Card className="mt-3 p-0">
          <ul className="divide-y divide-slate-100">
            {items.map((item, index) => {
              const key = `${item.kind}-${item.timestamp}-${index}`;
              const isLong = item.detail.length > DETAIL_TRUNCATE_AT;
              const isOpen = expanded.has(key);
              const detail =
                isLong && !isOpen
                  ? `${item.detail.slice(0, DETAIL_TRUNCATE_AT)}…`
                  : item.detail;
              return (
                <li key={key} className="px-5 py-4">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <KindBadge kind={item.kind} />
                    <span className="text-xs text-ink-400">
                      {formatTimestamp(item.timestamp)}
                    </span>
                    {item.case_id !== null && (
                      <Link
                        href={`/cases/${item.case_id}`}
                        className="text-xs font-semibold text-accent-600 hover:text-accent-700"
                      >
                        View case →
                      </Link>
                    )}
                  </div>
                  <p className="mt-2 text-sm break-words text-ink-900">
                    {detail}
                    {isLong && (
                      <button
                        type="button"
                        onClick={() => toggle(key)}
                        className="ml-2 text-xs font-semibold text-accent-600 hover:text-accent-700"
                      >
                        {isOpen ? "Show less" : "Show more"}
                      </button>
                    )}
                  </p>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Cases table
// ---------------------------------------------------------------------------

function CasesSection({
  cases,
  rowErrors,
  busyCaseId,
  onPause,
  onResume,
}: {
  cases: AdminCase[];
  rowErrors: Record<string, string>;
  busyCaseId: string | null;
  onPause: (caseId: string) => void;
  onResume: (caseId: string) => void;
}) {
  return (
    <section aria-label="All cases">
      <h2 className="text-base font-semibold tracking-tight">All cases</h2>
      <Card className="mt-3 overflow-x-auto p-0">
        {cases.length === 0 ? (
          <p className="px-5 py-5 text-sm text-ink-600">No cases yet.</p>
        ) : (
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-medium tracking-wide text-ink-600 uppercase">
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Company</th>
                <th className="px-5 py-3">User</th>
                <th className="px-5 py-3">Amount</th>
                <th className="px-5 py-3">Updated</th>
                <th className="px-5 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {cases.map((c) => {
                const rowError = rowErrors[c.id];
                return (
                  <tr key={c.id} className="align-middle">
                    <td className="px-5 py-3">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-5 py-3 font-medium text-ink-900">
                      <Link
                        href={`/cases/${c.id}`}
                        className="hover:text-accent-600"
                      >
                        {c.company_name}
                      </Link>
                      <span className="mt-0.5 block text-xs font-normal text-ink-400">
                        {humanize(c.category)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-ink-600">{c.user_email}</td>
                    <td className="px-5 py-3 text-ink-900">
                      {formatAmount(c.requested_amount, "USD") ?? "—"}
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap text-ink-600">
                      {formatTimestamp(c.updated_at)}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex flex-col items-end gap-1">
                        {c.status === "BLOCKED" ? (
                          <Button
                            variant="secondary"
                            disabled={busyCaseId === c.id}
                            onClick={() => onResume(c.id)}
                            className="min-h-9 px-3 py-1.5 text-xs"
                          >
                            Resume
                          </Button>
                        ) : isPausable(c.status) ? (
                          <Button
                            variant="danger"
                            disabled={busyCaseId === c.id}
                            onClick={() => onPause(c.id)}
                            className="min-h-9 px-3 py-1.5 text-xs"
                          >
                            Pause
                          </Button>
                        ) : null}
                        {rowError !== undefined && (
                          <p
                            role="alert"
                            className="max-w-56 text-right text-xs font-medium text-red-700"
                          >
                            {rowError}
                          </p>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Console
// ---------------------------------------------------------------------------

export function AdminConsole() {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [gateError, setGateError] = useState<string | null>(null);

  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [queue, setQueue] = useState<InterventionItem[] | null>(null);
  const [cases, setCases] = useState<AdminCase[] | null>(null);
  const [killSwitchActive, setKillSwitchActive] = useState<boolean | null>(
    null,
  );
  const [channels, setChannels] = useState<AdminChannel[] | null>(null);
  const [busyChannelId, setBusyChannelId] = useState<string | null>(null);
  const [events, setEvents] = useState<AdminClaimEvent[] | null>(null);
  const [busyEventId, setBusyEventId] = useState<string | null>(null);
  const [researching, setResearching] = useState(false);
  const [researchResult, setResearchResult] = useState<string | null>(null);

  const [loadError, setLoadError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [busyCaseId, setBusyCaseId] = useState<string | null>(null);
  const [togglingKillSwitch, setTogglingKillSwitch] = useState(false);

  const inFlight = useRef(false);

  useEffect(() => {
    setToken(getStoredAdminToken());
    setReady(true);
  }, []);

  const handleForbidden = useCallback(() => {
    clearAdminToken();
    setToken(null);
    setMetrics(null);
    setQueue(null);
    setCases(null);
    setKillSwitchActive(null);
    setGateError("Admin token rejected (403). Please enter a valid token.");
  }, []);

  const refresh = useCallback(
    async (activeToken: string) => {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const [
          metricsResult,
          queueResult,
          casesResult,
          killSwitchResult,
          channelsResult,
          eventsResult,
        ] = await Promise.all([
          getAdminMetrics(activeToken),
          getInterventionQueue(activeToken),
          listAdminCases(activeToken),
          getKillSwitch(activeToken),
          listChannels(activeToken),
          listAdminEvents(activeToken, "draft"),
        ]);
        setMetrics(metricsResult);
        setQueue(queueResult);
        setCases(casesResult);
        setKillSwitchActive(killSwitchResult.kill_switch_active);
        setChannels(channelsResult);
        setEvents(eventsResult);
        setLoadError(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          handleForbidden();
        } else {
          setLoadError(
            err instanceof Error
              ? err.message
              : "Could not reach the KarenBot API.",
          );
        }
      } finally {
        inFlight.current = false;
      }
    },
    [handleForbidden],
  );

  async function handleChannelAction(
    channelId: string,
    action: "verify" | "deactivate",
  ) {
    if (token === null) return;
    if (
      action === "deactivate" &&
      !window.confirm("Reject this channel? It will be hidden from Karen.")
    ) {
      return;
    }
    setBusyChannelId(channelId);
    try {
      if (action === "verify") await verifyChannel(token, channelId);
      else await deactivateChannel(token, channelId);
      await refresh(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) handleForbidden();
      else
        setLoadError(
          err instanceof Error ? err.message : "Channel action failed.",
        );
    } finally {
      setBusyChannelId(null);
    }
  }

  async function handleEventAction(eventId: string, action: "publish" | "reject") {
    if (token === null) return;
    if (
      action === "reject" &&
      !window.confirm("Reject this event? It will never be shown to users.")
    ) {
      return;
    }
    setBusyEventId(eventId);
    try {
      if (action === "publish") await publishEvent(token, eventId);
      else await rejectEvent(token, eventId);
      await refresh(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) handleForbidden();
      else
        setLoadError(
          err instanceof Error ? err.message : "Event action failed.",
        );
    } finally {
      setBusyEventId(null);
    }
  }

  async function handleResearch() {
    if (token === null) return;
    setResearching(true);
    setResearchResult(null);
    try {
      const counts = await runEventResearch(token);
      setResearchResult(
        `Research done: ${counts.proposed} proposed, ${counts.created} new drafts, ${counts.skipped} skipped (duplicates or unusable).`,
      );
      await refresh(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) handleForbidden();
      else
        setResearchResult(
          `Research failed: ${err instanceof Error ? err.message : "unknown error"}`,
        );
    } finally {
      setResearching(false);
    }
  }

  useEffect(() => {
    if (token === null) return;
    void refresh(token);
    const interval = window.setInterval(() => {
      void refresh(token);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [token, refresh]);

  const handleToggleKillSwitch = async () => {
    if (token === null || killSwitchActive === null) return;
    const next = !killSwitchActive;
    const message = next
      ? "Activate the KILL SWITCH? All agent actions will be denied platform-wide."
      : "Deactivate the kill switch? Agent actions will resume platform-wide.";
    if (!window.confirm(message)) return;
    setTogglingKillSwitch(true);
    try {
      const result = await setKillSwitch(token, next);
      setKillSwitchActive(result.kill_switch_active);
      await refresh(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        handleForbidden();
      } else {
        setLoadError(
          err instanceof Error ? err.message : "Kill switch toggle failed.",
        );
      }
    } finally {
      setTogglingKillSwitch(false);
    }
  };

  const handleCaseAction = async (
    caseId: string,
    action: "pause" | "resume",
  ) => {
    if (token === null) return;
    setBusyCaseId(caseId);
    setRowErrors((prev) => {
      const next = { ...prev };
      delete next[caseId];
      return next;
    });
    try {
      if (action === "pause") await pauseCase(token, caseId);
      else await resumeCase(token, caseId);
      await refresh(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        handleForbidden();
      } else {
        const detail =
          err instanceof ApiError
            ? err.detail
            : err instanceof Error
              ? err.message
              : "Action failed.";
        setRowErrors((prev) => ({ ...prev, [caseId]: detail }));
      }
    } finally {
      setBusyCaseId(null);
    }
  };

  if (!ready) return null;

  if (token === null) {
    return (
      <TokenGate
        error={gateError}
        onSubmit={(value) => {
          storeAdminToken(value);
          setGateError(null);
          setToken(value);
        }}
      />
    );
  }

  return (
    <div className="min-h-dvh bg-slate-50">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Link
              href="/dashboard"
              className="text-xs font-semibold text-accent-600 hover:text-accent-700"
            >
              ← Dashboard
            </Link>
            <h1 className="mt-1 text-xl font-semibold tracking-tight">
              Admin console
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              onClick={() => void refresh(token)}
              className="min-h-9 px-4 py-2 text-xs"
            >
              Refresh
            </Button>
            <Button
              variant="danger"
              disabled={togglingKillSwitch || killSwitchActive === null}
              onClick={() => void handleToggleKillSwitch()}
              className={
                killSwitchActive === true
                  ? "border-red-600 bg-red-600 text-white hover:border-red-700 hover:bg-red-700"
                  : ""
              }
            >
              {killSwitchActive === true
                ? "KILL SWITCH: ON — deactivate"
                : "KILL SWITCH: OFF — activate"}
            </Button>
          </div>
        </header>

        {killSwitchActive === true && (
          <div
            role="alert"
            className="mt-5 rounded-xl border border-red-300 bg-red-600 px-5 py-4 text-sm font-semibold text-white"
          >
            KILL SWITCH ACTIVE — all agent actions are denied platform-wide
          </div>
        )}

        {loadError !== null && (
          <Card className="mt-5 border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-700">
              Could not load admin data: {loadError}
            </p>
            <p className="mt-1 text-sm text-red-700/80">
              Is the API running at the configured NEXT_PUBLIC_API_URL?
            </p>
          </Card>
        )}

        {metrics === null || queue === null || cases === null ? (
          loadError === null && (
            <div className="flex items-center justify-center py-16">
              <p className="text-sm text-ink-400">Loading admin console…</p>
            </div>
          )
        ) : (
          <div className="mt-6 space-y-8">
            <MetricsSection metrics={metrics} />
            {channels !== null && (
              <ChannelsSection
                channels={channels}
                busyChannelId={busyChannelId}
                onVerify={(id) => void handleChannelAction(id, "verify")}
                onDeactivate={(id) =>
                  void handleChannelAction(id, "deactivate")
                }
              />
            )}
            {events !== null && (
              <EventsSection
                events={events}
                busyEventId={busyEventId}
                researching={researching}
                researchResult={researchResult}
                onPublish={(id) => void handleEventAction(id, "publish")}
                onReject={(id) => void handleEventAction(id, "reject")}
                onResearch={() => void handleResearch()}
              />
            )}
            <InterventionQueueSection items={queue} />
            <CasesSection
              cases={cases}
              rowErrors={rowErrors}
              busyCaseId={busyCaseId}
              onPause={(caseId) => void handleCaseAction(caseId, "pause")}
              onResume={(caseId) => void handleCaseAction(caseId, "resume")}
            />
          </div>
        )}
      </div>
    </div>
  );
}

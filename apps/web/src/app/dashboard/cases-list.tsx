"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, ButtonLink } from "@/components/Button";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import {
  ApiError,
  createCase,
  formatAmount,
  humanize,
  listCases,
  scanInbox,
  seed,
  type Case,
  type ClaimCandidate,
} from "@/lib/api";

/** Badge styling per candidate kind: amber = expiring/owed travel money,
 *  red = you were double-charged, slate = merchandise that never arrived. */
const KIND_BADGE_CLASSES: Record<string, string> = {
  unused_flight_credit: "border-amber-200 bg-amber-100 text-amber-800",
  cancelled_flight: "border-amber-200 bg-amber-100 text-amber-800",
  duplicate_charge: "border-red-200 bg-red-100 text-red-700",
  failed_delivery: "border-slate-200 bg-slate-100 text-ink-600",
};

function KindBadge({ kind }: { kind: string }) {
  const classes =
    KIND_BADGE_CLASSES[kind] ?? "border-slate-200 bg-slate-100 text-ink-600";
  return (
    <span
      className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${classes}`}
    >
      {humanize(kind)}
    </span>
  );
}

function InboxScanPanel() {
  const router = useRouter();
  const [scanning, setScanning] = useState(false);
  const [scanSource, setScanSource] = useState<"mock" | "live" | null>(null);
  const [candidates, setCandidates] = useState<ClaimCandidate[] | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [startingRef, setStartingRef] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  async function handleScan() {
    setScanning(true);
    setScanError(null);
    setStartError(null);
    try {
      const result = await scanInbox();
      setCandidates(result.candidates);
      setScanSource(result.source);
      setDismissed(new Set());
    } catch (err) {
      setCandidates(null);
      setScanError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Could not scan your inbox — try again.",
      );
    } finally {
      setScanning(false);
    }
  }

  async function startCase(candidate: ClaimCandidate) {
    setStartingRef(candidate.reference);
    setStartError(null);
    try {
      const numeric =
        candidate.amount !== null && candidate.amount !== ""
          ? Number(candidate.amount)
          : null;
      const created = await createCase({
        company_name: candidate.company_name,
        category: candidate.suggested_category,
        description: `${candidate.title}. ${candidate.snippet}`,
        requested_amount:
          numeric !== null && !Number.isNaN(numeric) ? numeric : null,
        company_industry: candidate.company_industry,
      });
      router.push(`/cases/${created.case.id}`);
    } catch (err) {
      setStartError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Could not start the case — try again.",
      );
      setStartingRef(null);
    }
  }

  function dismiss(reference: string) {
    setDismissed((prev) => new Set(prev).add(reference));
  }

  const visible =
    candidates?.filter((c) => !dismissed.has(c.reference)) ?? null;

  return (
    <section aria-label="Inbox scan">
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void handleScan()} disabled={scanning}>
          {scanning ? "Karen is reading your inbox…" : "Scan my inbox for money"}
        </Button>
        <ButtonLink href="/cases/new" variant="secondary">
          Start a new case
        </ButtonLink>
      </div>

      {scanError !== null && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800"
        >
          {scanError}
        </p>
      )}

      {startError !== null && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
        >
          Could not start the case: {startError}
        </p>
      )}

      {visible !== null &&
        (visible.length === 0 ? (
          <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-ink-600">
            Inbox looks clean — nothing worth chasing right now.
          </p>
        ) : (
          <div className="mt-6">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold">Karen found money</h2>
              {scanSource === "mock" && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                  Demo data — connect your email to scan your real inbox
                </span>
              )}
            </div>
            <ul className="mt-3 flex flex-col gap-4">
              {visible.map((candidate) => {
                const amount = formatAmount(candidate.amount, "USD");
                const starting = startingRef === candidate.reference;
                return (
                  <li key={candidate.reference}>
                    <Card className="relative border-accent-500/40">
                      <button
                        type="button"
                        aria-label={`Dismiss: ${candidate.title}`}
                        onClick={() => dismiss(candidate.reference)}
                        className="absolute top-3 right-3 flex size-8 items-center justify-center rounded-lg text-lg leading-none text-ink-400 hover:bg-slate-100 hover:text-ink-900"
                      >
                        ×
                      </button>
                      <div className="flex items-start justify-between gap-4 pr-8">
                        <div>
                          <KindBadge kind={candidate.kind} />
                          <h3 className="mt-2 text-base font-bold">
                            {candidate.title}
                          </h3>
                          <p className="mt-1 text-sm leading-relaxed text-ink-600">
                            {candidate.snippet}
                          </p>
                          <p className="mt-1 text-xs text-ink-400">
                            {candidate.company_name}
                            {" · "}
                            {humanize(candidate.suggested_category)}
                          </p>
                        </div>
                        {amount !== null && (
                          <span className="text-2xl font-bold whitespace-nowrap text-ink-900">
                            {amount}
                          </span>
                        )}
                      </div>
                      <div className="mt-4">
                        <Button
                          disabled={startingRef !== null}
                          onClick={() => void startCase(candidate)}
                        >
                          {starting ? "Starting…" : "Start a case"}
                        </Button>
                      </div>
                    </Card>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
    </section>
  );
}

export function CasesList() {
  const [cases, setCases] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Idempotent: creates the demo user + companies on first run.
        await seed();
        const result = await listCases();
        if (!cancelled) setCases(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not reach the KarenBot API.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error !== null) {
    return (
      <div className="px-8 py-10">
        <Card className="border-red-200 bg-red-50">
          <p className="text-sm font-medium text-red-700">
            Could not load your cases: {error}
          </p>
          <p className="mt-1 text-sm text-red-700/80">
            Is the API running at the configured NEXT_PUBLIC_API_URL?
          </p>
        </Card>
      </div>
    );
  }

  if (cases === null) {
    return (
      <div className="flex flex-1 items-center justify-center px-8 py-16">
        <p className="text-sm text-ink-400">Loading cases…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col px-8 py-8">
      <InboxScanPanel />

      {cases.length === 0 ? (
        <div className="flex flex-1 items-center justify-center py-16">
          <div className="text-center">
            <div
              aria-hidden="true"
              className="mx-auto flex size-14 items-center justify-center rounded-full bg-accent-50 text-2xl"
            >
              📂
            </div>
            <h2 className="mt-5 text-lg font-semibold">No active cases yet</h2>
            <p className="mx-auto mt-2 max-w-sm text-sm text-ink-600">
              When you start a case, Karen will track every email, escalation,
              and refund here.
            </p>
            <div className="mt-6">
              <ButtonLink href="/cases/new">Start your first case</ButtonLink>
            </div>
          </div>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 lg:grid-cols-2">
          {cases.map((c) => {
            const amount = formatAmount(c.requested_amount, c.currency);
            return (
              <li key={c.id}>
                <Link href={`/cases/${c.id}`} className="block rounded-xl">
                  <Card className="transition-colors hover:border-accent-500/60">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="text-base font-semibold">
                          {c.company_name ?? "Unknown company"}
                        </h2>
                        <p className="mt-0.5 text-sm text-ink-600">
                          {humanize(c.category)}
                        </p>
                      </div>
                      <StatusBadge status={c.status} />
                    </div>
                    <div className="mt-4 flex items-center justify-between">
                      <span className="text-sm font-medium text-ink-900">
                        {amount ?? "Amount TBD"}
                      </span>
                      <span className="text-sm font-semibold text-accent-600">
                        View case →
                      </span>
                    </div>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

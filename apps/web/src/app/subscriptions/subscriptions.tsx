"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ApiError, formatAmount, seed } from "@/lib/api";
import {
  actOnSubscription,
  createLinkToken,
  exchangePublicToken,
  listConnections,
  listSubscriptions,
  refreshSubscriptions,
  revokeConnection,
  scanEmailSubscriptions,
  type BankConnection,
  type Subscription,
  type SubscriptionAction,
} from "@/lib/banking-api";

const CADENCE_LABELS: Record<Subscription["cadence"], string> = {
  weekly: "/wk",
  monthly: "/mo",
  yearly: "/yr",
};

const ACTION_BUTTONS: ReadonlyArray<{
  action: SubscriptionAction;
  label: string;
}> = [
  { action: "cancel", label: "Have Karen cancel it" },
  { action: "negotiate", label: "Negotiate it down" },
  { action: "refund", label: "Get a refund" },
];

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Could not reach the KarenBot API.";
}

export function Subscriptions() {
  const router = useRouter();
  const [connections, setConnections] = useState<BankConnection[] | null>(
    null,
  );
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [rescanning, setRescanning] = useState(false);
  const [emailScanning, setEmailScanning] = useState(false);
  /** Subscription id with an in-flight action (disables its buttons). */
  const [busyId, setBusyId] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    const [conns, subs] = await Promise.all([
      listConnections(),
      listSubscriptions(),
    ]);
    setConnections(conns.filter((c) => c.status !== "revoked"));
    setSubscriptions(subs);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await seed(); // idempotent — ensures the demo user exists
        await refetch();
        if (!cancelled) setError(null);
      } catch (err) {
        if (!cancelled) setError(describeError(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refetch]);

  async function connectBank() {
    setActionError(null);
    setConnecting(true);
    try {
      // Production uses Plaid Link in the browser; in dev/mock mode the
      // backend accepts the sentinel public token directly.
      await createLinkToken();
      await exchangePublicToken({
        public_token: "mock-public-token",
        institution_name: "Mock Bank of Dev",
      });
      await refetch();
    } catch (err) {
      setActionError(describeError(err));
    } finally {
      setConnecting(false);
    }
  }

  async function disconnect(connection: BankConnection) {
    const name = connection.institution_name ?? "this bank";
    if (
      !window.confirm(
        `Disconnect ${name}? Karen will stop scanning its transactions.`,
      )
    ) {
      return;
    }
    setActionError(null);
    try {
      await revokeConnection(connection.id);
      await refetch();
    } catch (err) {
      setActionError(describeError(err));
    }
  }

  async function rescan() {
    setActionError(null);
    setRescanning(true);
    try {
      const subs = await refreshSubscriptions();
      setSubscriptions(subs);
    } catch (err) {
      setActionError(describeError(err));
    } finally {
      setRescanning(false);
    }
  }

  async function scanEmail() {
    setActionError(null);
    setEmailScanning(true);
    try {
      const subs = await scanEmailSubscriptions();
      setSubscriptions(subs);
    } catch (err) {
      setActionError(describeError(err));
    } finally {
      setEmailScanning(false);
    }
  }

  async function act(sub: Subscription, action: SubscriptionAction) {
    setActionError(null);
    setBusyId(sub.id);
    try {
      const result = await actOnSubscription(sub.id, action);
      if (action === "dismiss" || result.case_id === undefined) {
        await refetch();
        return;
      }
      router.push(`/cases/${result.case_id}`);
      return; // keep buttons disabled while navigating
    } catch (err) {
      setActionError(describeError(err));
    }
    setBusyId(null);
  }

  if (error !== null && connections === null) {
    return (
      <Card className="border-red-200 bg-red-50">
        <p className="text-sm font-medium text-red-700">
          Could not load subscriptions: {error}
        </p>
      </Card>
    );
  }

  if (connections === null) {
    return <p className="text-sm text-ink-400">Loading subscriptions…</p>;
  }

  const sorted = [...subscriptions].sort(
    (a, b) => Number(b.yearly_cost) - Number(a.yearly_cost),
  );
  const active = sorted.filter((s) => s.status !== "dismissed");
  const dismissed = sorted.filter((s) => s.status === "dismissed");
  const totalYearly = active.reduce(
    (sum, s) => sum + Number(s.yearly_cost),
    0,
  );

  return (
    <div className="flex flex-col gap-6">
      {actionError !== null && (
        <p
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
        >
          {actionError}
        </p>
      )}

      {connections.length === 0 && subscriptions.length === 0 ? (
        /* Hero — nothing detected yet */
        <Card className="flex flex-col items-start gap-4 bg-face-100 p-8">
          <h2 className="font-display text-2xl tracking-tight">
            Find bills you forgot you were paying
          </h2>
          <p className="max-w-xl text-sm leading-relaxed text-ink-600">
            Karen hunts recurring charges — gym memberships, streaming
            services, that app you tried once — then cancels them, negotiates
            them down, or claws your money back. Two ways to find them:
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={emailScanning} onClick={() => void scanEmail()}>
              {emailScanning
                ? "Reading your receipts…"
                : "Scan my email for subscriptions"}
            </Button>
            <Button
              variant="secondary"
              disabled={connecting}
              onClick={() => void connectBank()}
            >
              {connecting
                ? "Connecting & scanning transactions…"
                : "Connect a bank account (demo)"}
            </Button>
          </div>
          <p className="text-xs text-ink-400">
            The email scan reads billing receipts in your connected inbox,
            only when you click. Bank data catches more (some subscriptions
            never email) — in production that opens Plaid Link, a secure bank
            login; KarenBot never sees your credentials.
          </p>
        </Card>
      ) : (
        <>
          {/* Connections + scans */}
          <div className="flex flex-wrap items-center gap-3">
            {connections.map((connection) => (
              <span
                key={connection.id}
                className="inline-flex items-center gap-2 rounded-full border-2 border-black bg-white py-1.5 pr-1.5 pl-3.5 text-sm"
              >
                <span className="font-bold">
                  {connection.institution_name ?? connection.provider}
                </span>
                <button
                  type="button"
                  onClick={() => void disconnect(connection)}
                  className="rounded-full px-2.5 py-1 text-xs font-bold text-accent-600 hover:bg-accent-50"
                >
                  Disconnect
                </button>
              </span>
            ))}
            {connections.length > 0 && (
              <Button
                variant="secondary"
                disabled={rescanning}
                onClick={() => void rescan()}
              >
                {rescanning ? "Scanning…" : "Re-scan bank"}
              </Button>
            )}
            <Button
              variant="secondary"
              disabled={emailScanning}
              onClick={() => void scanEmail()}
            >
              {emailScanning ? "Reading receipts…" : "Scan email receipts"}
            </Button>
          </div>

          {/* Summary bar */}
          {active.length > 0 && (
            <div className="rounded-xl border-2 border-black bg-accent-500 px-5 py-4 text-white shadow-[4px_4px_0_0_#000]">
              <p className="font-display text-base">
                {active.length} recurring{" "}
                {active.length === 1 ? "charge" : "charges"} ≈{" "}
                {formatAmount(
                  String(totalYearly),
                  active[0]?.currency ?? "USD",
                ) ?? `$${totalYearly}`}
                /yr
              </p>
            </div>
          )}

          {/* Subscription cards */}
          {active.length === 0 && dismissed.length === 0 ? (
            <Card>
              <p className="text-sm text-ink-400">
                No recurring charges detected yet — hit Re-scan after new
                transactions sync.
              </p>
            </Card>
          ) : (
            <ul className="flex flex-col gap-4">
              {active.map((sub) => {
                const busy = busyId === sub.id;
                const amount = formatAmount(sub.amount, sub.currency);
                const yearly = formatAmount(sub.yearly_cost, sub.currency);
                return (
                  <li key={sub.id}>
                    <Card>
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <h3 className="text-base font-bold">
                            {sub.merchant_name}
                          </h3>
                          <p className="mt-1 text-sm text-ink-600">
                            {amount}
                            {CADENCE_LABELS[sub.cadence]} —{" "}
                            <span className="font-bold text-ink-900">
                              ≈ {yearly}/yr
                            </span>
                          </p>
                          <p className="mt-1 text-xs text-ink-400">
                            Seen {sub.occurrences}{" "}
                            {sub.occurrences === 1 ? "time" : "times"}
                            {sub.last_seen !== null
                              ? ` — last on ${new Date(
                                  sub.last_seen,
                                ).toLocaleDateString()}`
                              : ""}
                            {sub.source === "email_scan"
                              ? " — from email receipts"
                              : ""}
                          </p>
                        </div>
                        {sub.status === "case_created" &&
                          sub.case_id !== null && (
                            <span className="inline-flex items-center gap-2">
                              <span className="rounded-full border-[1.5px] border-black bg-bob-100 px-2.5 py-0.5 text-xs font-bold">
                                Karen is on it
                              </span>
                              <Link
                                href={`/cases/${sub.case_id}`}
                                className="text-sm font-bold text-accent-600 underline"
                              >
                                View case
                              </Link>
                            </span>
                          )}
                        {sub.status === "canceled" && (
                          <span className="rounded-full border-[1.5px] border-black bg-money-100 px-3 py-1 text-xs font-bold text-money-700">
                            Canceled — saving ≈ {yearly}/yr
                          </span>
                        )}
                      </div>

                      {sub.status === "detected" && (
                        <div className="mt-4">
                          <div className="flex flex-wrap items-center gap-3">
                            {ACTION_BUTTONS.map(({ action, label }) => (
                              <Button
                                key={action}
                                variant="secondary"
                                disabled={busy}
                                onClick={() => void act(sub, action)}
                              >
                                {label}
                              </Button>
                            ))}
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void act(sub, "dismiss")}
                              className="min-h-11 px-2 text-sm font-medium text-ink-400 hover:text-ink-600 disabled:opacity-50"
                            >
                              Dismiss
                            </button>
                          </div>
                          {!sub.company_targetable && (
                            <p className="mt-2 text-xs text-ink-400">
                              Small/unknown merchant — Karen will draft the
                              message for you to send yourself (we don&apos;t
                              go after small businesses).
                            </p>
                          )}
                        </div>
                      )}
                    </Card>
                  </li>
                );
              })}
            </ul>
          )}

          {/* Dismissed */}
          {dismissed.length > 0 && (
            <details className="rounded-xl border-2 border-black bg-face-100">
              <summary className="cursor-pointer px-5 py-3 text-sm font-bold text-ink-600">
                Dismissed ({dismissed.length})
              </summary>
              <ul className="border-t-2 border-dashed border-black px-5 py-3">
                {dismissed.map((sub) => (
                  <li
                    key={sub.id}
                    className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-2 text-sm text-ink-400 last:border-b-0"
                  >
                    <span>{sub.merchant_name}</span>
                    <span>
                      {formatAmount(sub.amount, sub.currency)}
                      {CADENCE_LABELS[sub.cadence]}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import {
  ApiError,
  listConnectedAccounts,
  revokeConnectedAccount,
  seed,
  startConnect,
  type ConnectedAccount,
} from "@/lib/api";

const PROVIDER_LABELS: Record<string, string> = {
  google: "Gmail",
  microsoft: "Outlook",
  imap_smtp: "IMAP/SMTP",
};

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Could not reach the KarenBot API.";
}

export function ConnectedAccounts() {
  const [accounts, setAccounts] = useState<ConnectedAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refetch = useCallback(async () => {
    setAccounts(await listConnectedAccounts());
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await seed(); // idempotent — ensures the demo user exists in dev
        if (!cancelled) await refetch();
      } catch (err) {
        if (!cancelled) setError(describeError(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refetch]);

  async function connectGmail() {
    setError(null);
    setBusy(true);
    try {
      const { auth_url } = await startConnect("google");
      window.location.href = auth_url; // Google's consent screen
    } catch (err) {
      setError(describeError(err));
      setBusy(false);
    }
  }

  async function revoke(account: ConnectedAccount) {
    if (
      !window.confirm(
        `Disconnect ${account.provider_account_id}? Karen loses mailbox access immediately.`,
      )
    ) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await revokeConnectedAccount(account.id);
      await refetch();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  if (error !== null && accounts === null) {
    return (
      <p className="rounded-xl border-2 border-black bg-accent-50 px-4 py-3 text-sm font-bold text-accent-700">
        Could not load accounts: {error}
      </p>
    );
  }

  if (accounts === null) {
    return <p className="text-sm text-ink-400">Loading accounts…</p>;
  }

  const active = accounts.filter((a) => a.status === "active");

  return (
    <div className="flex flex-col gap-6">
      {error !== null && (
        <p
          role="alert"
          className="rounded-xl border-2 border-black bg-accent-50 px-4 py-3 text-sm font-bold text-accent-700"
        >
          {error}
        </p>
      )}

      {accounts.length === 0 && (
        <Card className="bg-face-100">
          <p className="text-sm leading-relaxed text-ink-600">
            No email connected yet. Connect one and Karen can scan it for
            claimable money, case evidence, and subscriptions.
          </p>
        </Card>
      )}

      <ul className="flex flex-col gap-4">
        {accounts.map((account) => (
          <li key={account.id}>
            <Card className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-base font-bold">
                  {account.provider_account_id}
                </p>
                <p className="mt-0.5 text-sm text-ink-600">
                  {PROVIDER_LABELS[account.provider] ?? account.provider} —
                  connected{" "}
                  {new Date(account.created_at).toLocaleDateString()}
                </p>
              </div>
              {account.status === "active" ? (
                <div className="flex items-center gap-3">
                  <span className="rounded-full border-[1.5px] border-black bg-money-100 px-2.5 py-0.5 text-xs font-bold text-money-700">
                    Active
                  </span>
                  <Button
                    variant="danger"
                    disabled={busy}
                    onClick={() => void revoke(account)}
                  >
                    Disconnect
                  </Button>
                </div>
              ) : (
                <span className="rounded-full border-[1.5px] border-black bg-face-100 px-2.5 py-0.5 text-xs font-bold text-ink-600">
                  {account.status}
                </span>
              )}
            </Card>
          </li>
        ))}
      </ul>

      <div>
        <Button disabled={busy} onClick={() => void connectGmail()}>
          {busy
            ? "Opening Google…"
            : active.length > 0
              ? "Reconnect Gmail"
              : "Connect Gmail"}
        </Button>
        <p className="mt-2 max-w-xl text-xs leading-relaxed text-ink-400">
          Heads up: while the Google app is in testing mode, connections
          expire every 7 days — if scans start saying “reconnect your email,”
          come back here and reconnect. Reconnecting replaces the old grant
          for the same address.
        </p>
      </div>
    </div>
  );
}

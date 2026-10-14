"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ButtonLink } from "@/components/Button";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import {
  formatAmount,
  humanize,
  listCases,
  seed,
  type Case,
} from "@/lib/api";

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

  if (cases.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center px-8 py-16">
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
    );
  }

  return (
    <div className="px-8 py-8">
      <ul className="grid gap-4 lg:grid-cols-2">
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
      <div className="mt-8">
        <ButtonLink href="/cases/new">Start a new case</ButtonLink>
      </div>
    </div>
  );
}

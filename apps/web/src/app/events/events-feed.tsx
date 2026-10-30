"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import {
  addMyCompany,
  listEvents,
  listMyCompanies,
  removeMyCompany,
  scanCompanies,
  type ClaimEventSummary,
  type UserCompany,
} from "@/lib/api";

/** Parse "YYYY-MM-DD" in local time (new Date(iso) would shift by TZ). */
export function parseDay(iso: string): Date {
  const [y = 1970, m = 1, d = 1] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function dayLabel(iso: string): string {
  const day = parseDay(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - day.getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return day.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function groupByDay(
  events: ClaimEventSummary[],
): { date: string; events: ClaimEventSummary[] }[] {
  const groups = new Map<string, ClaimEventSummary[]>();
  for (const event of events) {
    const bucket = groups.get(event.event_date) ?? [];
    bucket.push(event);
    groups.set(event.event_date, bucket);
  }
  // listEvents returns newest-first; Map preserves insertion order.
  return [...groups.entries()].map(([date, dayEvents]) => ({
    date,
    events: dayEvents,
  }));
}

function EventCard({
  event,
  mine,
}: {
  event: ClaimEventSummary;
  mine: boolean;
}) {
  return (
    <Link href={`/events/${event.id}`} className="block rounded-2xl">
      <article className="rounded-2xl border-2 border-black bg-white p-5 shadow-[4px_4px_0_0_#000] transition-[transform,box-shadow] hover:-translate-x-px hover:-translate-y-px hover:shadow-[6px_6px_0_0_#000]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-bold">{event.company_name}</span>
          {mine && (
            <span className="rounded-full border-[1.5px] border-black bg-accent-100 px-2 py-0.5 text-xs font-bold text-accent-700">
              You use this
            </span>
          )}
          {event.region !== null && (
            <span className="rounded-full border-[1.5px] border-black bg-face-100 px-2 py-0.5 text-xs font-bold text-ink-600">
              {event.region}
            </span>
          )}
          {event.claim_deadline !== null && (
            <span className="rounded-full border-[1.5px] border-black bg-bob-100 px-2 py-0.5 text-xs font-bold">
              Claim by {dayLabel(event.claim_deadline)}
            </span>
          )}
        </div>
        <h3 className="mt-2 text-base font-bold">{event.title}</h3>
        <p className="mt-1 text-sm leading-relaxed font-bold text-money-700">
          {event.entitlement}
        </p>
        <p className="mt-2 text-sm font-bold text-accent-600 underline">
          Were you affected?
        </p>
      </article>
    </Link>
  );
}

/** The user's visible, editable "companies you use" profile. */
function MyCompaniesPanel({
  companies,
  onChanged,
}: {
  companies: UserCompany[];
  onChanged: () => Promise<void>;
}) {
  const [scanning, setScanning] = useState(false);
  const [scanNote, setScanNote] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleScan() {
    setScanning(true);
    setScanNote(null);
    try {
      const result = await scanCompanies();
      setScanNote(
        result.found.length === 0
          ? "No recognizable companies found in your recent mail."
          : `Found ${result.found.length} compan${result.found.length === 1 ? "y" : "ies"} in your inbox (${result.added} new).` +
              (result.source === "mock" ? " (Demo inbox.)" : ""),
      );
      await onChanged();
    } catch (err) {
      setScanNote(
        err instanceof Error ? err.message : "Could not scan your inbox.",
      );
    } finally {
      setScanning(false);
    }
  }

  async function handleAdd() {
    const name = newName.trim();
    if (name === "") return;
    setBusy(true);
    try {
      await addMyCompany(name);
      setNewName("");
      await onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(id: string) {
    setBusy(true);
    try {
      await removeMyCompany(id);
      await onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-label="Companies you use"
      className="rounded-2xl border-2 border-black bg-face-100 p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg">Companies you use</h2>
        <Button variant="secondary" disabled={scanning} onClick={() => void handleScan()}>
          {scanning ? "Reading your inbox…" : "Find them in my inbox"}
        </Button>
      </div>
      <p className="mt-1 max-w-xl text-xs leading-relaxed text-ink-600">
        Karen flags events from these companies for you. The inbox scan runs
        only when you click it, keeps only recognizable company names, and
        you can remove anything here.
      </p>
      {scanNote !== null && (
        <p className="mt-2 text-xs font-bold text-ink-600">{scanNote}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {companies.map((company) => (
          <span
            key={company.id}
            className="inline-flex items-center gap-1.5 rounded-full border-2 border-black bg-white px-3 py-1 text-sm font-bold"
          >
            {company.company_name}
            <button
              type="button"
              aria-label={`Remove ${company.company_name}`}
              disabled={busy}
              onClick={() => void handleRemove(company.id)}
              className="text-ink-400 hover:text-accent-600"
            >
              ×
            </button>
          </span>
        ))}
        {companies.length === 0 && (
          <span className="text-sm text-ink-400">
            None yet — scan your inbox or add one.
          </span>
        )}
      </div>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void handleAdd();
        }}
      >
        <input
          type="text"
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="Add a company, e.g. Verizon"
          aria-label="Add a company"
          className="min-h-10 flex-1 rounded-xl border-2 border-black bg-white px-3 text-sm sm:max-w-60"
        />
        <Button type="submit" variant="secondary" disabled={busy}>
          Add
        </Button>
      </form>
    </section>
  );
}

export function EventsFeed() {
  const [events, setEvents] = useState<ClaimEventSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // null = signed out (or profile unavailable): feed stays unpersonalized.
  const [myCompanies, setMyCompanies] = useState<UserCompany[] | null>(null);

  async function refreshCompanies() {
    try {
      setMyCompanies(await listMyCompanies());
    } catch {
      setMyCompanies(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await listEvents(7);
        if (!cancelled) setEvents(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Could not load events.",
          );
        }
      }
      try {
        const companies = await listMyCompanies();
        if (!cancelled) setMyCompanies(companies);
      } catch {
        // Signed out — the feed just isn't personalized.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error !== null) {
    return (
      <p className="rounded-xl border-2 border-black bg-accent-50 px-4 py-3 text-sm font-bold text-accent-700">
        Could not load this week&apos;s events: {error}
      </p>
    );
  }

  if (events === null) {
    return <p className="text-sm text-ink-400">Loading this week…</p>;
  }

  const myNames = new Set(
    (myCompanies ?? []).map((c) => c.company_name.toLowerCase()),
  );
  const matched = events.filter((e) =>
    myNames.has(e.company_name.toLowerCase()),
  );
  const rest = events.filter(
    (e) => !myNames.has(e.company_name.toLowerCase()),
  );

  return (
    <div className="flex flex-col gap-8">
      {myCompanies !== null && (
        <MyCompaniesPanel
          companies={myCompanies}
          onChanged={refreshCompanies}
        />
      )}

      {matched.length > 0 && (
        <section aria-label="Events that affect you">
          <h2 className="font-display text-lg tracking-tight text-accent-600">
            These affect you
          </h2>
          <ul className="mt-3 flex flex-col gap-4">
            {matched.map((event) => (
              <li key={event.id}>
                <EventCard event={event} mine />
              </li>
            ))}
          </ul>
        </section>
      )}

      {events.length === 0 ? (
        <div className="py-12 text-center">
          <Image
            src="/karen.png"
            alt=""
            width={96}
            height={97}
            className="mx-auto"
            aria-hidden="true"
          />
          <h2 className="mt-5 font-display text-xl">
            A quiet week, apparently
          </h2>
          <p className="mx-auto mt-2 max-w-sm text-sm text-ink-600">
            No published events in the last 7 days. Companies will mess up
            again soon — check back.
          </p>
        </div>
      ) : (
        groupByDay(rest).map((group) => (
          <section key={group.date} aria-label={dayLabel(group.date)}>
            <h2 className="font-display text-lg tracking-tight">
              {dayLabel(group.date)}
            </h2>
            <ul className="mt-3 flex flex-col gap-4">
              {group.events.map((event) => (
                <li key={event.id}>
                  <EventCard event={event} mine={false} />
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}

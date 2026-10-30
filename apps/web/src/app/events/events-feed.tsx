"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { listEvents, type ClaimEventSummary } from "@/lib/api";

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

export function EventsFeed() {
  const [events, setEvents] = useState<ClaimEventSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  if (events.length === 0) {
    return (
      <div className="py-12 text-center">
        <Image
          src="/karen.png"
          alt=""
          width={96}
          height={97}
          className="mx-auto"
          aria-hidden="true"
        />
        <h2 className="mt-5 font-display text-xl">A quiet week, apparently</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm text-ink-600">
          No published events in the last 7 days. Companies will mess up again
          soon — check back.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {groupByDay(events).map((group) => (
        <section key={group.date} aria-label={dayLabel(group.date)}>
          <h2 className="font-display text-lg tracking-tight">
            {dayLabel(group.date)}
          </h2>
          <ul className="mt-3 flex flex-col gap-4">
            {group.events.map((event) => (
              <li key={event.id}>
                <Link href={`/events/${event.id}`} className="block rounded-2xl">
                  <article className="rounded-2xl border-2 border-black bg-white p-5 shadow-[4px_4px_0_0_#000] transition-[transform,box-shadow] hover:-translate-x-px hover:-translate-y-px hover:shadow-[6px_6px_0_0_#000]">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-bold">
                        {event.company_name}
                      </span>
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
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

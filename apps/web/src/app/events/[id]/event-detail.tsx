"use client";

import { useEffect, useState } from "react";
import { ButtonLink } from "@/components/Button";
import { getEvent, type ClaimEventDetail } from "@/lib/api";
import { dayLabel } from "../events-feed";

export function EventDetail({ eventId }: { eventId: string }) {
  const [event, setEvent] = useState<ClaimEventDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await getEvent(eventId);
        if (!cancelled) setEvent(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Could not load this event.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  if (error !== null) {
    return (
      <p className="rounded-xl border-2 border-black bg-accent-50 px-4 py-3 text-sm font-bold text-accent-700">
        Could not load this event: {error}
      </p>
    );
  }

  if (event === null) {
    return <p className="text-sm text-ink-400">Loading event…</p>;
  }

  return (
    <article>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-bold">{event.company_name}</span>
        <span className="text-sm text-ink-400">
          {dayLabel(event.event_date)}
        </span>
        {event.region !== null && (
          <span className="rounded-full border-[1.5px] border-black bg-face-100 px-2 py-0.5 text-xs font-bold text-ink-600">
            {event.region}
          </span>
        )}
      </div>
      <h1 className="mt-2 font-display text-3xl leading-tight tracking-tight">
        {event.title}
      </h1>
      <p className="mt-4 max-w-xl leading-relaxed text-ink-600">
        {event.summary}
      </p>

      <div className="mt-8 rounded-2xl border-2 border-black bg-money-100 p-6 shadow-[4px_4px_0_0_#000]">
        <h2 className="font-display text-lg">What you&apos;re owed</h2>
        <p className="mt-2 leading-relaxed font-bold text-money-700">
          {event.entitlement}
        </p>
        {event.claim_deadline !== null && (
          <p className="mt-2 text-sm font-bold">
            Claim deadline: {dayLabel(event.claim_deadline)}
          </p>
        )}
      </div>

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <section>
          <h2 className="text-base font-bold">Who qualifies</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-600">
            {event.eligibility}
          </p>
        </section>
        <section>
          <h2 className="text-base font-bold">How to claim it yourself</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-600">
            {event.how_to_claim}
          </p>
        </section>
      </div>

      <div className="mt-8 rounded-2xl border-2 border-black bg-face-100 p-6">
        <h2 className="font-display text-lg">Or don&apos;t lift a finger</h2>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-600">
          Tell Karen how this hit you and she&apos;ll handle the asking, the
          arguing, and the waiting on hold that happens over email.
        </p>
        <div className="mt-4">
          <ButtonLink href={`/cases/new?event=${event.id}`}>
            I was affected — put Karen on it
          </ButtonLink>
        </div>
      </div>

      {event.source_urls.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm font-bold">Sources</h2>
          <ul className="mt-2 flex flex-col gap-1">
            {event.source_urls.map((url) => (
              <li key={url}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm break-all text-accent-600 underline"
                >
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="mt-8 text-xs leading-relaxed text-ink-400">
        Eligibility is ultimately the company&apos;s call under its own policy
        — Karen&apos;s job is to argue your side of it. KarenBot is not a law
        firm and does not provide legal advice.
      </p>
    </article>
  );
}

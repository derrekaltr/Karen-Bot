import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { EventsFeed } from "./events-feed";

export const metadata: Metadata = {
  title: "What's owed — KarenBot",
  description:
    "Outages, meltdowns, and recalls from the past week where companies' own policies owe affected customers money.",
};

export default function EventsPage() {
  return (
    <div className="min-h-dvh">
      <AppHeader
        right={
          <Link
            href="/dashboard"
            className="text-sm font-bold text-ink-600 underline hover:text-ink-900"
          >
            Dashboard
          </Link>
        }
      />
      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="font-display text-3xl tracking-tight">
          What&apos;s owed this week
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-600">
          Public outages, meltdowns, and recalls where the company&apos;s own
          published policy owes affected customers something. If one of these
          hit you, click in — Karen will tell you what you&apos;re owed and go
          get it.
        </p>
        <div className="mt-8">
          <EventsFeed />
        </div>
      </main>
    </div>
  );
}

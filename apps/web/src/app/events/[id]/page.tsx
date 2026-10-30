import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { EventDetail } from "./event-detail";

export const metadata: Metadata = {
  title: "Claimable event — KarenBot",
};

export default async function EventPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="min-h-dvh">
      <AppHeader
        right={
          <Link
            href="/events"
            className="text-sm font-bold text-ink-600 underline hover:text-ink-900"
          >
            All events
          </Link>
        }
      />
      <main className="mx-auto max-w-3xl px-6 py-10">
        <EventDetail eventId={id} />
      </main>
    </div>
  );
}

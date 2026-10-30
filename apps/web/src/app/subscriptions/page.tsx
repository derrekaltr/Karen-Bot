import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { Subscriptions } from "./subscriptions";

export const metadata: Metadata = {
  title: "Subscriptions — KarenBot",
};

export default function SubscriptionsPage() {
  return (
    <div className="min-h-dvh">
      <AppHeader
        right={
          <Link
            href="/dashboard"
            className="text-sm font-bold text-ink-600 underline hover:text-ink-900"
          >
            Back to dashboard
          </Link>
        }
      />
      <main className="mx-auto max-w-4xl px-6 py-10">
        <h1 className="font-display text-3xl tracking-tight">Subscriptions</h1>
        <p className="mt-2 text-sm text-ink-600">
          Recurring charges Karen found on your linked accounts — cancel them,
          talk them down, or claw the money back.
        </p>
        <div className="mt-6">
          <Subscriptions />
        </div>
      </main>
    </div>
  );
}

import Link from "next/link";
import type { Metadata } from "next";
import { Subscriptions } from "./subscriptions";

export const metadata: Metadata = {
  title: "Subscriptions — KarenBot",
};

export default function SubscriptionsPage() {
  return (
    <div className="min-h-dvh">
      <header className="border-b border-slate-100">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Karen<span className="text-accent-600">Bot</span>
          </Link>
          <Link
            href="/dashboard"
            className="text-sm font-medium text-ink-600 hover:text-ink-900"
          >
            Back to dashboard
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-10">
        <h1 className="text-xl font-semibold tracking-tight">Subscriptions</h1>
        <p className="mt-1 text-sm text-ink-600">
          Recurring charges Karen found on your linked accounts.
        </p>
        <div className="mt-6">
          <Subscriptions />
        </div>
      </main>
    </div>
  );
}

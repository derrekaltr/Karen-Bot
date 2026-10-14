import Link from "next/link";
import type { Metadata } from "next";
import { GuidedIntake } from "./intake";

export const metadata: Metadata = {
  title: "New Case — KarenBot",
};

export default function NewCasePage() {
  return (
    <div className="min-h-dvh">
      <header className="border-b border-slate-100">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
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

      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-2xl font-bold tracking-tight">Start a new case</h1>
        <p className="mt-2 text-sm text-ink-600">
          Tell Karen what happened — she&apos;ll walk you through it.
        </p>
        <div className="mt-8">
          <GuidedIntake />
        </div>
      </main>
    </div>
  );
}

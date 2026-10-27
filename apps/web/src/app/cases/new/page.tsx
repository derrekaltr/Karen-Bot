import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { GuidedIntake } from "./intake";

export const metadata: Metadata = {
  title: "New Case — KarenBot",
};

export default function NewCasePage() {
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

      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="font-display text-3xl tracking-tight">
          Start a new case
        </h1>
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

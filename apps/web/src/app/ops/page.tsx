import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { OpsConsole } from "./ops-console";

export const metadata: Metadata = {
  title: "Ops Council — KarenBot",
};

export default function OpsPage() {
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
        <h1 className="font-display text-3xl tracking-tight">Ops Council</h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-600">
          The company&apos;s shared desk: send each other concepts and
          proposals for review, approve or request changes, and read what the
          research agent found.
        </p>
        <div className="mt-8">
          <OpsConsole />
        </div>
      </main>
    </div>
  );
}

import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { ConnectedAccounts } from "./connected-accounts";

export const metadata: Metadata = {
  title: "Connected Accounts — KarenBot",
};

export default function AccountsPage() {
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
          Connected accounts
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-600">
          The email Karen scans for receipts, evidence, and subscriptions.
          Scans only run when you click them, and you can disconnect here any
          time — credentials are dropped immediately.
        </p>
        <div className="mt-8">
          <ConnectedAccounts />
        </div>
      </main>
    </div>
  );
}

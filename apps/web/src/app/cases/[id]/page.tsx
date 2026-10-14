import Link from "next/link";
import type { Metadata } from "next";
import { CaseDetail } from "./case-detail";

export const metadata: Metadata = {
  title: "Case — KarenBot",
};

export default async function CasePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
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
        <CaseDetail caseId={id} />
      </main>
    </div>
  );
}

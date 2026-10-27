import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
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
        <CaseDetail caseId={id} />
      </main>
    </div>
  );
}

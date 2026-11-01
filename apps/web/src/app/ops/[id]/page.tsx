import Link from "next/link";
import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { OpsItemView } from "./item-view";

export const metadata: Metadata = {
  title: "Ops item — KarenBot",
};

export default async function OpsItemPage({
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
            href="/ops"
            className="text-sm font-bold text-ink-600 underline hover:text-ink-900"
          >
            Back to the council
          </Link>
        }
      />
      <main className="mx-auto max-w-3xl px-6 py-10">
        <OpsItemView itemId={id} />
      </main>
    </div>
  );
}

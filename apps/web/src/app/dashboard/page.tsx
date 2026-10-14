import Link from "next/link";
import type { Metadata } from "next";
import { ButtonLink } from "@/components/Button";

export const metadata: Metadata = {
  title: "Dashboard — KarenBot",
};

const navItems = [
  { label: "Cases", href: "/dashboard" },
  { label: "New Case", href: "/cases/new" },
  { label: "Recoveries", href: "/dashboard" },
  { label: "Connected Accounts", href: "/dashboard" },
  { label: "Billing", href: "/dashboard" },
  { label: "Settings", href: "/dashboard" },
] as const;

export default function DashboardPage() {
  return (
    <div className="flex min-h-dvh flex-col sm:flex-row">
      <aside className="border-b border-slate-200 bg-slate-50 sm:min-h-dvh sm:w-64 sm:border-r sm:border-b-0">
        <div className="px-6 py-5">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Karen<span className="text-accent-600">Bot</span>
          </Link>
        </div>
        <nav aria-label="Dashboard" className="px-3 pb-4">
          <ul className="flex flex-row gap-1 overflow-x-auto sm:flex-col">
            {navItems.map((item) => (
              <li key={item.label}>
                <Link
                  href={item.href}
                  className="block rounded-lg px-3 py-2.5 text-sm font-medium whitespace-nowrap text-ink-600 hover:bg-slate-200/60 hover:text-ink-900"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="border-b border-slate-100 px-8 py-5">
          <h1 className="text-xl font-semibold tracking-tight">Cases</h1>
        </header>
        <div className="flex flex-1 items-center justify-center px-8 py-16">
          <div className="text-center">
            <div
              aria-hidden="true"
              className="mx-auto flex size-14 items-center justify-center rounded-full bg-accent-50 text-2xl"
            >
              📂
            </div>
            <h2 className="mt-5 text-lg font-semibold">No active cases yet</h2>
            <p className="mx-auto mt-2 max-w-sm text-sm text-ink-600">
              When you start a case, Karen will track every email, escalation,
              and refund here.
            </p>
            <div className="mt-6">
              <ButtonLink href="/cases/new">Start your first case</ButtonLink>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

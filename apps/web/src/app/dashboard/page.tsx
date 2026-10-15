import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import type { Metadata } from "next";
import { CasesList } from "./cases-list";

export const metadata: Metadata = {
  title: "Dashboard — KarenBot",
};

const navItems = [
  { label: "Cases", href: "/dashboard" },
  { label: "New Case", href: "/cases/new" },
  { label: "Subscriptions", href: "/subscriptions" },
  { label: "Recoveries", href: "/dashboard" },
  { label: "Connected Accounts", href: "/dashboard" },
  { label: "Billing", href: "/dashboard" },
  { label: "Settings", href: "/dashboard" },
] as const;

export default function DashboardPage() {
  return (
    <div className="flex min-h-dvh flex-col sm:flex-row">
      <aside className="border-b border-slate-200 bg-slate-50 sm:min-h-dvh sm:w-64 sm:border-r sm:border-b-0">
        <div className="flex items-center justify-between px-6 py-5">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Karen<span className="text-accent-600">Bot</span>
          </Link>
          <UserButton />
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
          <div className="mt-2 sm:mt-4 sm:border-t sm:border-slate-200 sm:pt-3">
            <Link
              href="/admin"
              className="block rounded-lg px-3 py-2 text-xs font-medium text-ink-400 hover:bg-slate-200/60 hover:text-ink-600"
            >
              Admin
            </Link>
          </div>
        </nav>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="border-b border-slate-100 px-8 py-5">
          <h1 className="text-xl font-semibold tracking-tight">Cases</h1>
        </header>
        <CasesList />
      </main>
    </div>
  );
}

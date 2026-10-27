import Image from "next/image";
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
      <aside className="border-b-2 border-black bg-face-100 sm:min-h-dvh sm:w-64 sm:border-r-2 sm:border-b-0">
        <div className="flex items-center justify-between px-5 py-4">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/karen.png"
              alt=""
              width={36}
              height={37}
              className="-my-1"
            />
            <span className="font-display text-lg tracking-tight">
              KarenBot
            </span>
          </Link>
          <UserButton />
        </div>
        <nav aria-label="Dashboard" className="px-3 pb-4">
          <ul className="flex flex-row gap-1 overflow-x-auto sm:flex-col">
            {navItems.map((item) => (
              <li key={item.label}>
                <Link
                  href={item.href}
                  className="block rounded-xl px-3 py-2.5 text-sm font-bold whitespace-nowrap text-ink-600 hover:bg-white hover:text-ink-900"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-2 sm:mt-4 sm:border-t-2 sm:border-black/10 sm:pt-3">
            <Link
              href="/admin"
              className="block rounded-xl px-3 py-2 text-xs font-bold text-ink-400 hover:bg-white hover:text-ink-600"
            >
              Admin
            </Link>
          </div>
        </nav>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="border-b-2 border-black px-8 py-5">
          <h1 className="font-display text-2xl tracking-tight">Cases</h1>
        </header>
        <CasesList />
      </main>
    </div>
  );
}

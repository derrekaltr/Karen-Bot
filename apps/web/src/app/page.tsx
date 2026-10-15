import Link from "next/link";
import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { ButtonLink } from "@/components/Button";
import { Card } from "@/components/Card";

const steps = [
  {
    number: "1",
    title: "Connect your email",
    description:
      "Securely link the inbox where your receipts and order confirmations live. Karen finds the evidence for you.",
  },
  {
    number: "2",
    title: "Tell Karen what happened",
    description:
      "Describe the problem in plain English — a chat or a quick form. Karen asks the right follow-up questions.",
  },
  {
    number: "3",
    title: "Karen negotiates and you get paid",
    description:
      "Karen escalates politely but relentlessly until the company makes it right. Refunds land in your account.",
  },
] as const;

export default function LandingPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-slate-100">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Karen<span className="text-accent-600">Bot</span>
          </Link>
          <nav aria-label="Main" className="flex items-center gap-3">
            <Show when="signed-out">
              <SignInButton>
                <button className="inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-semibold text-slate-700 hover:text-slate-900">
                  Sign in
                </button>
              </SignInButton>
              <SignUpButton>
                <button className="inline-flex min-h-11 items-center rounded-lg bg-accent-600 px-4 text-sm font-semibold text-white hover:bg-accent-700">
                  Get started
                </button>
              </SignUpButton>
            </Show>
            <Show when="signed-in">
              <ButtonLink href="/dashboard" variant="secondary">
                Dashboard
              </ButtonLink>
              <UserButton />
            </Show>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-6 py-20 text-center sm:py-28">
          <p className="mb-4 inline-block rounded-full bg-accent-50 px-4 py-1.5 text-sm font-medium text-accent-700">
            Your personal consumer advocate
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-balance sm:text-6xl">
            Stop fighting customer service.{" "}
            <span className="text-accent-600">KarenBot does it for you.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-600">
            Late deliveries, broken products, surprise fees. KarenBot handles
            the emails, the escalations, and the hold music — and doesn&apos;t
            stop until you&apos;re made whole.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <ButtonLink href="/cases/new">Start a case</ButtonLink>
            <ButtonLink href="/dashboard" variant="secondary">
              See how it works
            </ButtonLink>
          </div>
        </section>

        <section
          aria-labelledby="how-it-works"
          className="border-t border-slate-100 bg-slate-50"
        >
          <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
            <h2
              id="how-it-works"
              className="text-center text-3xl font-bold tracking-tight"
            >
              How it works
            </h2>
            <ol className="mt-12 grid gap-6 sm:grid-cols-3">
              {steps.map((step) => (
                <li key={step.number}>
                  <Card className="h-full">
                    <span
                      aria-hidden="true"
                      className="flex size-10 items-center justify-center rounded-full bg-accent-600 text-base font-bold text-white"
                    >
                      {step.number}
                    </span>
                    <h3 className="mt-4 text-lg font-semibold">
                      {step.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-ink-600">
                      {step.description}
                    </p>
                  </Card>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-100">
        <div className="mx-auto max-w-5xl px-6 py-8 text-center">
          <p className="text-sm text-ink-400">
            KarenBot is not a law firm and does not provide legal advice.
          </p>
          <p className="mt-2 text-sm text-ink-400">
            &copy; {new Date().getFullYear()} KarenBot
          </p>
        </div>
      </footer>
    </div>
  );
}

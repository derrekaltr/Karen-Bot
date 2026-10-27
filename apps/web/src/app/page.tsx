import Image from "next/image";
import Link from "next/link";
import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { ButtonLink } from "@/components/Button";

const steps = [
  {
    number: "1",
    title: "Tell Karen what happened",
    description:
      "Plain English is fine. Canceled flight, dead internet, order that never showed — Karen asks the right follow-ups and pulls the receipts from your inbox.",
  },
  {
    number: "2",
    title: "Karen takes it up with them",
    description:
      "She writes to the company's real support channel as your authorized representative, citing their own published policies back at them.",
  },
  {
    number: "3",
    title: "You get paid",
    description:
      "Lowball voucher? She counters. Silence? She follows up. You approve the final offer, and the refund lands where it belongs.",
  },
] as const;

// Real entitlements from the policy database — the leverage Karen cites.
const leverage = [
  {
    company: "AT&T",
    fact: "Fiber down 20 minutes? Their own guarantee owes you a full day's bill credit.",
  },
  {
    company: "Marriott",
    fact: "Walked from a confirmed room? $200 cash plus 90,000 points, per their guarantee.",
  },
  {
    company: "JetBlue",
    fact: "Controllable delay over 3 hours? 5,000 points, automatic — if anyone checks.",
  },
  {
    company: "Airlines (all US)",
    fact: "Canceled flight? Federal rules say cash refund — not the voucher they offer first.",
  },
] as const;

const bigTargets = [
  "Delta",
  "Comcast",
  "Uber",
  "Amazon",
  "American Express",
  "McDonald's",
] as const;

export default function LandingPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b-2 border-black bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/karen.png"
              alt=""
              width={40}
              height={41}
              priority
              className="-my-1"
            />
            <span className="font-display text-xl tracking-tight">
              KarenBot
            </span>
          </Link>
          <nav aria-label="Main" className="flex items-center gap-3">
            <Show when="signed-out">
              <SignInButton>
                <button className="inline-flex min-h-11 items-center rounded-xl px-4 text-sm font-bold hover:underline">
                  Sign in
                </button>
              </SignInButton>
              <SignUpButton>
                <button className="inline-flex min-h-11 items-center rounded-xl border-2 border-black bg-accent-500 px-4 text-sm font-bold text-white shadow-[3px_3px_0_0_#000] transition-[transform,box-shadow] hover:translate-x-px hover:translate-y-px hover:bg-accent-600 hover:shadow-[2px_2px_0_0_#000]">
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
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-16 sm:py-24 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h1 className="font-display text-5xl leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl">
              <span className="whitespace-nowrap">They owe you.</span>
              <br />
              <span className="whitespace-nowrap">Karen collects.</span>
            </h1>
            <p className="mt-6 max-w-md text-lg leading-relaxed text-ink-600">
              Canceled flights. Dead internet. Orders that never showed. Karen
              argues with the company — politely, relentlessly, in writing —
              until they make it right.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <ButtonLink href="/cases/new">Put Karen on it</ButtonLink>
              <ButtonLink href="#how-it-works" variant="secondary">
                See how she works
              </ButtonLink>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-md pt-36 sm:pt-44">
            <Image
              src="/karen.png"
              alt="Karen, a robot with a manager-ready bob haircut"
              width={366}
              height={371}
              priority
              className="absolute right-6 top-0 w-40 sm:w-48"
            />
            <div className="relative z-10 rounded-2xl border-2 border-black bg-white shadow-[6px_6px_0_0_#000]">
              <div className="flex items-center justify-between gap-3 border-b-2 border-dashed border-black px-5 py-3">
                <p className="text-sm font-bold">
                  Case #0847 — Acme Air, canceled flight
                </p>
                <span className="inline-flex items-center rounded-full border-[1.5px] border-black bg-money-100 px-2.5 py-1 text-xs font-bold text-money-700">
                  Won
                </span>
              </div>
              <div className="space-y-4 px-5 py-4 text-sm leading-relaxed">
                <div>
                  <p className="font-bold">Karen</p>
                  <p className="text-ink-600">
                    My client&apos;s flight was canceled. Under federal refund
                    rules that&apos;s cash back to his card — which I&apos;d
                    like processed this week.
                  </p>
                </div>
                <div className="rounded-xl bg-face-100 p-3">
                  <p className="font-bold">Acme Air</p>
                  <p className="text-ink-600">
                    We&apos;re pleased to offer a $75 travel voucher for the
                    inconvenience.
                  </p>
                </div>
                <div>
                  <p className="font-bold">Karen</p>
                  <p className="text-ink-600">
                    A voucher is not a refund. I&apos;ll wait.
                  </p>
                </div>
              </div>
              <div className="border-t-2 border-dashed border-black px-5 py-3">
                <p className="text-sm font-bold text-money-700">
                  $347.00 refunded to original payment
                </p>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="leverage" className="bg-black text-white">
          <div className="mx-auto max-w-6xl px-6 py-14">
            <h2 id="leverage" className="font-display text-3xl tracking-tight">
              Companies wrote these rules. Karen read them.
            </h2>
            <p className="mt-2 max-w-xl text-white/70">
              Published guarantees, service-level credits, federal entitlements
              — the fine print says they owe you. Most people never ask.
            </p>
            <ul className="mt-8 grid gap-4 sm:grid-cols-2">
              {leverage.map((item) => (
                <li
                  key={item.company}
                  className="rounded-2xl border-2 border-white/90 p-5"
                >
                  <p className="font-bold text-bob-400">{item.company}</p>
                  <p className="mt-1 text-sm leading-relaxed text-white/90">
                    {item.fact}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section aria-labelledby="how-heading" id="how-it-works">
          <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
            <h2
              id="how-heading"
              className="font-display text-3xl tracking-tight"
            >
              How it works
            </h2>
            <ol className="mt-10 grid gap-6 sm:grid-cols-3">
              {steps.map((step) => (
                <li
                  key={step.number}
                  className="rounded-2xl border-2 border-black bg-white p-6 shadow-[4px_4px_0_0_#000]"
                >
                  <span
                    aria-hidden="true"
                    className="flex size-11 items-center justify-center rounded-xl border-2 border-black bg-bob-400 font-display text-lg"
                  >
                    {step.number}
                  </span>
                  <h3 className="mt-4 text-lg font-bold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-600">
                    {step.description}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section
          aria-labelledby="punch-up"
          className="border-y-2 border-black bg-face-100"
        >
          <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 sm:py-20 lg:grid-cols-2">
            <div>
              <h2
                id="punch-up"
                className="font-display text-3xl tracking-tight"
              >
                Karen only punches up.
              </h2>
              <p className="mt-4 max-w-md leading-relaxed text-ink-600">
                She goes after airlines, telecoms, banks, and billion-dollar
                apps — companies with policy teams and compensation budgets.
                Small businesses are off limits, permanently, and that rule is
                built into her code, not her mood.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {bigTargets.map((name) => (
                <span
                  key={name}
                  className="rounded-full border-2 border-black bg-white px-4 py-2 text-sm font-bold"
                >
                  {name}
                </span>
              ))}
              <span className="relative mt-3 mr-6 inline-block">
                <span className="inline-block rounded-full border-2 border-dashed border-ink-400 px-4 py-2 text-sm font-bold text-ink-400 line-through">
                  Rosa&apos;s Corner Bakery
                </span>
                <span className="absolute -top-3 -right-6 -rotate-6 rounded-lg border-2 border-accent-500 bg-white px-2 py-0.5 text-xs font-bold text-accent-600">
                  Off limits
                </span>
              </span>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-20 text-center sm:py-24">
          <h2 className="mx-auto max-w-2xl font-display text-4xl leading-tight tracking-tight sm:text-5xl">
            Karen would like to speak with a manager.
          </h2>
          <p className="mx-auto mt-4 max-w-md text-lg text-ink-600">
            Point her at a company that owes you, and get on with your day.
          </p>
          <div className="mt-8 flex justify-center">
            <ButtonLink href="/cases/new">Start a case</ButtonLink>
          </div>
        </section>
      </main>

      <footer className="border-t-2 border-black">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-6 py-8 text-center">
          <p className="text-sm text-ink-400">
            KarenBot is not a law firm and does not provide legal advice. Karen
            writes as your authorized representative — and if a company asks
            whether she&apos;s automated, she tells the truth.
          </p>
          <p className="text-sm text-ink-400">
            &copy; {new Date().getFullYear()} KarenBot
          </p>
        </div>
      </footer>
    </div>
  );
}

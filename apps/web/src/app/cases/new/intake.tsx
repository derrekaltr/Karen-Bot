"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import {
  ApiError,
  addEvidence,
  authorizeCase,
  completeIntake,
  createCase,
  initiateContact,
  listCompanies,
  seed,
  type Company,
} from "@/lib/api";

/** Category options for the two seeded companies. */
const CATEGORY_OPTIONS: Record<
  string,
  ReadonlyArray<{ value: string; label: string }>
> = {
  "Acme Air": [
    { value: "baggage_delay_expenses", label: "Delayed baggage expenses" },
  ],
  Chipotle: [{ value: "incorrect_charge", label: "Incorrect charge" }],
};

const EVIDENCE_TYPES = [
  { value: "receipt", label: "Receipt" },
  { value: "screenshot", label: "Screenshot" },
  { value: "boarding_pass", label: "Boarding pass" },
  { value: "other", label: "Other" },
] as const;

type Phase =
  | "loading"
  | "company"
  | "details"
  | "evidence"
  | "ineligible"
  | "authorize"
  | "contact";

interface Bubble {
  id: number;
  from: "karen" | "you";
  text: string;
}

const inputClasses =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm focus:border-accent-600";

export function GuidedIntake() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [transcript, setTranscript] = useState<Bubble[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Step 1 form state
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");

  // Step 2 state
  const [caseId, setCaseId] = useState<string | null>(null);
  const [evidenceType, setEvidenceType] = useState("receipt");
  const [evidenceSummary, setEvidenceSummary] = useState("");
  const [evidenceCount, setEvidenceCount] = useState(0);

  // Step 3 state
  const [signedName, setSignedName] = useState("");
  const [loaText, setLoaText] = useState<string | null>(null);

  const nextBubbleId = useRef(0);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  function say(from: Bubble["from"], text: string) {
    setTranscript((prev) => [
      ...prev,
      { id: nextBubbleId.current++, from, text },
    ]);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await seed(); // idempotent — safe if dashboard already seeded
        const result = await listCompanies();
        if (cancelled) return;
        setCompanies(result);
        say(
          "karen",
          "Hi, I'm Karen. Tell me what happened and I'll take it from here. Which company wronged you?",
        );
        setPhase("company");
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not reach the KarenBot API.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, phase]);

  function failWith(err: unknown) {
    setError(
      err instanceof ApiError
        ? err.detail
        : err instanceof Error
          ? err.message
          : "Something went wrong talking to the API.",
    );
  }

  function pickCompany(company: Company) {
    setError(null);
    setCompanyName(company.name);
    const options = CATEGORY_OPTIONS[company.name] ?? [];
    setCategory(options[0]?.value ?? "");
    say("you", company.name);
    say(
      "karen",
      `${company.name} — noted. What kind of issue is this, what happened, and how much are you owed? Give me the details below.`,
    );
    setPhase("details");
  }

  async function submitDetails() {
    if (companyName === null || category === "" || description.trim() === "") {
      setError("Pick a category and describe what happened first.");
      return;
    }
    setError(null);
    setBusy(true);
    const parsedAmount = amount.trim() === "" ? null : Number(amount);
    say(
      "you",
      `${description.trim()}${parsedAmount !== null ? ` (about $${parsedAmount})` : ""}`,
    );
    try {
      const created = await createCase({
        company_name: companyName,
        category,
        description: description.trim(),
        requested_amount: parsedAmount,
      });
      setCaseId(created.case.id);
      for (const question of created.karen_questions) {
        say("karen", question);
      }
      say(
        "karen",
        "Attach whatever proof you have — receipts, screenshots, boarding passes. Add each one below, then tell me when you're done.",
      );
      setPhase("evidence");
    } catch (err) {
      failWith(err);
    } finally {
      setBusy(false);
    }
  }

  async function submitEvidence() {
    if (caseId === null || evidenceSummary.trim() === "") {
      setError("Describe the evidence before adding it.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await addEvidence(caseId, {
        evidence_type: evidenceType,
        summary: evidenceSummary.trim(),
      });
      say(
        "you",
        `Evidence (${evidenceType.replace(/_/g, " ")}): ${evidenceSummary.trim()}`,
      );
      say("karen", "Logged it. Anything else, or are we done here?");
      setEvidenceSummary("");
      setEvidenceCount((n) => n + 1);
    } catch (err) {
      failWith(err);
    } finally {
      setBusy(false);
    }
  }

  async function finishIntake() {
    if (caseId === null) return;
    setError(null);
    setBusy(true);
    say("you", "Done adding evidence.");
    try {
      const result = await completeIntake(caseId);
      if (result.eligible) {
        say(
          "karen",
          `Good news — you have a real case here. ${
            result.basis !== null
              ? `Basis: ${result.basis}.`
              : "It qualifies under their own policy."
          } They owe you, and I intend to collect.`,
        );
        say(
          "karen",
          `One formality before I go after ${companyName ?? "them"}: I need your written authorization to act on your behalf. Type your full legal name below to sign the Letter of Authorization.`,
        );
        setPhase("authorize");
      } else {
        say(
          "karen",
          `I checked their policies, and unfortunately this one doesn't qualify. ${
            result.reasons.length > 0
              ? `Here's why: ${result.reasons.join("; ")}.`
              : ""
          } The case has been closed — I'm sorry, even I have standards I can't argue past.`,
        );
        setPhase("ineligible");
      }
    } catch (err) {
      failWith(err);
    } finally {
      setBusy(false);
    }
  }

  async function submitAuthorization() {
    if (caseId === null || signedName.trim() === "") {
      setError("Type your full name to sign.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const result = await authorizeCase(caseId, signedName.trim());
      say("you", `Signed: ${signedName.trim()}`);
      say(
        "karen",
        "Signed and sealed — your Letter of Authorization is below. I'm ready when you are.",
      );
      setLoaText(result.loa_text);
      setPhase("contact");
    } catch (err) {
      failWith(err);
    } finally {
      setBusy(false);
    }
  }

  async function sendKaren() {
    if (caseId === null) return;
    setError(null);
    setBusy(true);
    try {
      const result = await initiateContact(caseId);
      if (result.decision === "deny") {
        failWith(
          new ApiError(
            422,
            `Karen can't make contact yet: ${result.reasons.join("; ")}`,
          ),
        );
        return;
      }
      router.push(`/cases/${caseId}`);
    } catch (err) {
      failWith(err);
      setBusy(false);
    }
  }

  const categoryOptions =
    companyName !== null ? (CATEGORY_OPTIONS[companyName] ?? []) : [];

  return (
    <div>
      <Card className="p-0">
        <div className="max-h-[28rem] overflow-y-auto">
          <ul className="flex flex-col gap-4 p-6">
            {transcript.map((bubble) => (
              <li
                key={bubble.id}
                className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                  bubble.from === "karen"
                    ? "self-start bg-slate-100 text-ink-900"
                    : "self-end bg-accent-600 text-white"
                }`}
              >
                {bubble.text}
              </li>
            ))}
            {phase === "loading" && (
              <li className="self-start text-sm text-ink-400">
                Connecting to Karen…
              </li>
            )}
          </ul>
          <div ref={transcriptEndRef} />
        </div>

        <div className="border-t border-slate-200 p-4">
          {error !== null && (
            <p
              role="alert"
              className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
            >
              {error}
            </p>
          )}

          {phase === "company" && (
            <div>
              <p className="mb-2 text-sm font-medium">Pick the company</p>
              <ul className="flex flex-col gap-2">
                {companies.map((company) => (
                  <li key={company.id}>
                    <button
                      type="button"
                      disabled={!company.targetable}
                      onClick={() => pickCompany(company)}
                      className={`flex min-h-11 w-full items-center justify-between rounded-lg border px-4 py-2.5 text-left text-sm transition-colors ${
                        company.targetable
                          ? "border-slate-300 bg-white hover:border-accent-600 hover:bg-accent-50"
                          : "cursor-not-allowed border-slate-200 bg-slate-50 text-ink-400"
                      }`}
                    >
                      <span className="font-semibold">{company.name}</span>
                      {company.targetable ? (
                        <span className="text-xs text-ink-400">
                          {company.industry}
                        </span>
                      ) : (
                        <span className="max-w-[60%] text-right text-xs">
                          KarenBot only takes on large companies — we don&apos;t
                          go after small businesses
                        </span>
                      )}
                    </button>
                  </li>
                ))}
                {companies.length === 0 && (
                  <li className="text-sm text-ink-400">
                    No companies available yet.
                  </li>
                )}
              </ul>
            </div>
          )}

          {phase === "details" && (
            <form
              className="flex flex-col gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void submitDetails();
              }}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="category" className="text-sm font-medium">
                    Category
                  </label>
                  <select
                    id="category"
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                    className={inputClasses}
                  >
                    {categoryOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="amount" className="text-sm font-medium">
                    Amount owed (USD)
                  </label>
                  <input
                    id="amount"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    className={inputClasses}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="description" className="text-sm font-medium">
                  What happened?
                </label>
                <textarea
                  id="description"
                  rows={4}
                  placeholder="Give Karen the details — dates, order numbers, who you talked to…"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm"
                />
              </div>
              <div>
                <Button type="submit" disabled={busy}>
                  {busy ? "Sending…" : "Tell Karen"}
                </Button>
              </div>
            </form>
          )}

          {phase === "evidence" && (
            <form
              className="flex flex-col gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void submitEvidence();
              }}
            >
              <div className="grid gap-4 sm:grid-cols-[12rem_1fr]">
                <div className="flex flex-col gap-1.5">
                  <label
                    htmlFor="evidence-type"
                    className="text-sm font-medium"
                  >
                    Evidence type
                  </label>
                  <select
                    id="evidence-type"
                    value={evidenceType}
                    onChange={(event) => setEvidenceType(event.target.value)}
                    className={inputClasses}
                  >
                    {EVIDENCE_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label
                    htmlFor="evidence-summary"
                    className="text-sm font-medium"
                  >
                    What does it show?
                  </label>
                  <input
                    id="evidence-summary"
                    type="text"
                    placeholder="e.g. Receipt for $85 of toiletries bought while bag was missing"
                    value={evidenceSummary}
                    onChange={(event) =>
                      setEvidenceSummary(event.target.value)
                    }
                    className={inputClasses}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button type="submit" variant="secondary" disabled={busy}>
                  Add evidence
                </Button>
                <Button
                  disabled={busy}
                  onClick={() => {
                    void finishIntake();
                  }}
                >
                  {busy
                    ? "Working…"
                    : evidenceCount > 0
                      ? "Done adding evidence"
                      : "Skip — no evidence to add"}
                </Button>
              </div>
            </form>
          )}

          {phase === "ineligible" && (
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                onClick={() => router.push("/dashboard")}
              >
                Back to dashboard
              </Button>
            </div>
          )}

          {phase === "authorize" && (
            <form
              className="flex flex-col gap-3 sm:flex-row sm:items-end"
              onSubmit={(event) => {
                event.preventDefault();
                void submitAuthorization();
              }}
            >
              <div className="flex flex-1 flex-col gap-1.5">
                <label htmlFor="signed-name" className="text-sm font-medium">
                  Type your full name to sign
                </label>
                <input
                  id="signed-name"
                  type="text"
                  placeholder="e.g. Dana Example"
                  value={signedName}
                  onChange={(event) => setSignedName(event.target.value)}
                  className={inputClasses}
                />
              </div>
              <Button type="submit" disabled={busy}>
                {busy ? "Signing…" : "Authorize KarenBot"}
              </Button>
            </form>
          )}

          {phase === "contact" && (
            <div className="flex flex-col gap-4">
              {loaText !== null && (
                <details className="rounded-lg border border-slate-200 bg-slate-50">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">
                    Your signed Letter of Authorization
                  </summary>
                  <pre className="max-h-64 overflow-y-auto border-t border-slate-200 px-4 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
                    {loaText}
                  </pre>
                </details>
              )}
              <div>
                <Button disabled={busy} onClick={() => void sendKaren()}>
                  {busy ? "Dispatching…" : "Send Karen after them"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

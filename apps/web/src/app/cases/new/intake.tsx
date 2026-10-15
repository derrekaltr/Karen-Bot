"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import {
  ApiError,
  addEvidence,
  scanCaseEvidence,
  authorizeCase,
  completeIntake,
  createCase,
  getCategoryCatalog,
  humanize,
  initiateContact,
  listCompanies,
  seed,
  type CategoryCatalog,
  type CategoryOption,
  type Company,
} from "@/lib/api";

/**
 * Sentinel value for the "Something else…" category option. Never collides
 * with real category keys (the server normalizes those to snake_case words).
 */
const CUSTOM_CATEGORY = "__custom__";

/** Catalog label for a category key, humanized snake_case as fallback. */
function categoryLabel(key: string, catalog: CategoryCatalog | null): string {
  if (catalog !== null) {
    for (const group of [catalog.general, ...Object.values(catalog.by_industry)]) {
      const match = group.find((option) => option.key === key);
      if (match !== undefined) return match.label;
    }
  }
  return humanize(key);
}

/** Merge option groups in order, deduplicating by key. */
function dedupeOptions(groups: CategoryOption[][]): CategoryOption[] {
  const seen = new Set<string>();
  const merged: CategoryOption[] = [];
  for (const group of groups) {
    for (const option of group) {
      if (!seen.has(option.key)) {
        seen.add(option.key);
        merged.push(option);
      }
    }
  }
  return merged;
}

/**
 * Options for a known company: its claim types first, then the catalog's
 * suggestions for its industry, then the general assist-mode categories.
 */
function optionsForCompany(
  company: Company,
  catalog: CategoryCatalog | null,
): CategoryOption[] {
  return dedupeOptions([
    company.claim_types.map((key) => ({
      key,
      label: categoryLabel(key, catalog),
    })),
    catalog?.by_industry[company.industry] ?? [],
    catalog?.general ?? [],
  ]);
}

/** Options for an unknown company, from its user-picked industry. */
function optionsForIndustry(
  industry: string,
  catalog: CategoryCatalog | null,
): CategoryOption[] {
  return dedupeOptions([
    industry === "other" ? [] : (catalog?.by_industry[industry] ?? []),
    catalog?.general ?? [],
  ]);
}

const SMALL_BUSINESS_NOTE =
  "Karen doesn't pressure small businesses — she'll draft the message and you send it yourself.";

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
  const [catalog, setCatalog] = useState<CategoryCatalog | null>(null);
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [showOtherInput, setShowOtherInput] = useState(false);
  const [otherName, setOtherName] = useState("");
  const [otherIndustry, setOtherIndustry] = useState("other");
  const [category, setCategory] = useState("");
  const [customCategory, setCustomCategory] = useState("");
  const [description, setDescription] = useState("");

  // Step 2 state
  const [caseId, setCaseId] = useState<string | null>(null);
  const [contactMode, setContactMode] = useState<"agent" | "assist">("agent");
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
        const [result, categoryCatalog] = await Promise.all([
          listCompanies(),
          getCategoryCatalog(),
        ]);
        if (cancelled) return;
        setCompanies(result);
        setCatalog(categoryCatalog);
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
    setSelectedCompany(company);
    setCompanyName(company.name);
    setShowOtherInput(false);
    setCategory(optionsForCompany(company, catalog)[0]?.key ?? CUSTOM_CATEGORY);
    say("you", company.name);
    say(
      "karen",
      `${company.name} — noted. What kind of issue is this, what happened, and how much are you owed? Give me the details below.`,
    );
    setPhase("details");
  }

  function pickOtherCompany() {
    const name = otherName.trim();
    if (name === "") {
      setError("Type the company name first.");
      return;
    }
    setError(null);
    setSelectedCompany(null);
    setCompanyName(name);
    setCategory(
      optionsForIndustry(otherIndustry, catalog)[0]?.key ?? CUSTOM_CATEGORY,
    );
    say("you", name);
    say(
      "karen",
      `${name} — noted. What kind of issue is this, what happened, and how much are you owed? Give me the details below.`,
    );
    setPhase("details");
  }

  async function submitDetails() {
    const effectiveCategory =
      category === CUSTOM_CATEGORY ? customCategory.trim() : category;
    if (
      companyName === null ||
      category === "" ||
      description.trim() === ""
    ) {
      setError("Pick a category and describe what happened first.");
      return;
    }
    if (effectiveCategory === "") {
      setError("Describe what you're after first.");
      return;
    }
    setError(null);
    setBusy(true);
    say("you", description.trim());
    try {
      const created = await createCase({
        company_name: companyName,
        category: effectiveCategory,
        description: description.trim(),
        // Karen infers the amount from the story (and asks for a ballpark
        // only if she can't).
        requested_amount: null,
        // Only unknown companies need the user-picked industry hint.
        ...(selectedCompany === null
          ? { company_industry: otherIndustry }
          : {}),
      });
      setCaseId(created.case.id);
      setContactMode(created.case.contact_mode);
      if (created.case.contact_mode === "assist") {
        say(
          "karen",
          "One thing to know: this case runs in assist mode. I'll build your case and write the message, but you'll be the one to send it — it lands better coming straight from you.",
        );
      }
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

  async function scanEmailForEvidence() {
    if (caseId === null) return;
    setError(null);
    setBusy(true);
    say("you", "Scan my email for proof.");
    try {
      const result = await scanCaseEvidence(caseId);
      const found = result.attached;
      const demoNote =
        result.source === "mock"
          ? " (Heads up: I'm scanning a demo inbox until your real email is connected.)"
          : "";
      if (found.length === 0 && result.total_matches > 0) {
        say(
          "karen",
          `Nothing new — I already attached ${result.total_matches} item` +
            `${result.total_matches === 1 ? "" : "s"} from your inbox to this ` +
            `case earlier.${demoNote}`,
        );
        setEvidenceCount((n) => (n > 0 ? n : result.total_matches));
      } else if (found.length === 0) {
        say(
          "karen",
          "I didn't find anything matching in your inbox. You can add " +
            `evidence manually, or we can proceed without it.${demoNote}`,
        );
      } else {
        for (const item of found) {
          say("karen", `Found and attached: ${item.summary}`);
        }
        say(
          "karen",
          `That's ${found.length} piece${found.length === 1 ? "" : "s"} of ` +
            `evidence from your inbox. Anything else, or are we done here?${demoNote}`,
        );
        setEvidenceCount((n) => n + found.length);
      }
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

  // Known company: its claim types, then its industry's suggestions, then
  // the general assist-mode categories. Unknown company: the user-picked
  // industry's suggestions plus the general ones. Deduplicated by key.
  const categoryOptions =
    selectedCompany !== null
      ? optionsForCompany(selectedCompany, catalog)
      : optionsForIndustry(otherIndustry, catalog);

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
                      onClick={() => pickCompany(company)}
                      className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-left text-sm transition-colors hover:border-accent-600 hover:bg-accent-50"
                    >
                      <span className="flex items-center gap-2">
                        <span className="font-semibold">{company.name}</span>
                        {!company.targetable && (
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-ink-600">
                            assist mode
                          </span>
                        )}
                      </span>
                      <span className="text-xs text-ink-400">
                        {company.industry}
                      </span>
                    </button>
                  </li>
                ))}
                {companies.length === 0 && (
                  <li className="text-sm text-ink-400">
                    No companies available yet.
                  </li>
                )}
                <li>
                  {showOtherInput ? (
                    <form
                      className="rounded-lg border border-slate-300 bg-white p-4"
                      onSubmit={(event) => {
                        event.preventDefault();
                        pickOtherCompany();
                      }}
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                        <div className="flex flex-1 flex-col gap-1.5">
                          <label
                            htmlFor="other-company"
                            className="text-sm font-medium"
                          >
                            Who wronged you?
                          </label>
                          <input
                            id="other-company"
                            type="text"
                            autoFocus
                            placeholder="e.g. Rosa's Corner Bakery"
                            value={otherName}
                            onChange={(event) =>
                              setOtherName(event.target.value)
                            }
                            className={inputClasses}
                          />
                        </div>
                        <div className="flex flex-col gap-1.5 sm:w-52">
                          <label
                            htmlFor="other-industry"
                            className="text-sm font-medium"
                          >
                            What kind of company is it?
                          </label>
                          <select
                            id="other-industry"
                            value={otherIndustry}
                            onChange={(event) =>
                              setOtherIndustry(event.target.value)
                            }
                            className={inputClasses}
                          >
                            {(catalog?.industries ?? ["other"]).map(
                              (industry) => (
                                <option key={industry} value={industry}>
                                  {humanize(industry)}
                                </option>
                              ),
                            )}
                          </select>
                        </div>
                        <Button type="submit">That&apos;s them</Button>
                      </div>
                      <p className="mt-2 text-xs text-ink-500">
                        Karen can draft for any company. Direct agent
                        negotiation unlocks once we&apos;ve verified the
                        company&apos;s official support channels.
                      </p>
                    </form>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setError(null);
                        setShowOtherInput(true);
                      }}
                      className="flex min-h-11 w-full items-center rounded-lg border border-dashed border-slate-300 bg-white px-4 py-2.5 text-left text-sm font-semibold transition-colors hover:border-accent-600 hover:bg-accent-50"
                    >
                      Other company…
                    </button>
                  )}
                </li>
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
              {selectedCompany !== null && !selectedCompany.targetable && (
                <p className="rounded-lg bg-slate-50 px-4 py-2.5 text-xs leading-relaxed text-ink-600">
                  {SMALL_BUSINESS_NOTE}
                </p>
              )}
              <div className="grid gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="category" className="text-sm font-medium">
                    What are you after?
                  </label>
                  <select
                    id="category"
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                    className={inputClasses}
                  >
                    {categoryOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                    <option value={CUSTOM_CATEGORY}>Something else…</option>
                  </select>
                </div>
              </div>
              {category === CUSTOM_CATEGORY && (
                <div className="flex flex-col gap-1.5">
                  <label
                    htmlFor="custom-category"
                    className="text-sm font-medium"
                  >
                    Describe what you&apos;re after
                  </label>
                  <input
                    id="custom-category"
                    type="text"
                    autoFocus
                    placeholder="e.g. 'flight credits for flights I didn't take'"
                    value={customCategory}
                    onChange={(event) =>
                      setCustomCategory(event.target.value)
                    }
                    className={inputClasses}
                  />
                </div>
              )}
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
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => {
                    void scanEmailForEvidence();
                  }}
                >
                  {busy ? "Scanning…" : "Scan my email for proof"}
                </Button>
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
                  {busy
                    ? "Dispatching…"
                    : contactMode === "assist"
                      ? "Have Karen draft it"
                      : "Send Karen after them"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

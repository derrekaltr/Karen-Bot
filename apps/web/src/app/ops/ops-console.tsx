"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ApiError, seed } from "@/lib/api";
import {
  ITEM_KINDS,
  KIND_LABELS,
  addMember,
  createItem,
  getMe,
  listItems,
  listMembers,
  runResearch,
  type ItemKind,
  type OpsItem,
  type OpsMember,
} from "@/lib/ops-api";
import { KindPill, StatusPill } from "./badges";

type Tab = "inbox" | "all" | "research" | "team";

const TABS: { key: Tab; label: string }[] = [
  { key: "inbox", label: "For your review" },
  { key: "all", label: "Everything" },
  { key: "research", label: "Research" },
  { key: "team", label: "Team" },
];

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Could not reach the KarenBot API.";
}

function ItemRow({ item }: { item: OpsItem }) {
  return (
    <Link href={`/ops/${item.id}`} className="block rounded-2xl">
      <Card className="transition-[transform,box-shadow] hover:-translate-x-px hover:-translate-y-px hover:shadow-[6px_6px_0_0_#000]">
        <div className="flex flex-wrap items-center gap-2">
          <KindPill kind={item.kind} />
          <StatusPill status={item.status} />
          {item.comment_count > 0 && (
            <span className="text-xs font-bold text-ink-400">
              {item.comment_count}{" "}
              {item.comment_count === 1 ? "comment" : "comments"}
            </span>
          )}
        </div>
        <h3 className="mt-2 text-base font-bold">{item.title}</h3>
        <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-ink-600">
          {item.body}
        </p>
        <p className="mt-2 text-xs text-ink-400">
          From {item.created_by_email}
          {item.reviewer_email !== null
            ? ` — for ${item.reviewer_email} to review`
            : ""}
        </p>
      </Card>
    </Link>
  );
}

function NewItemForm({
  members,
  me,
  onCreated,
}: {
  members: OpsMember[];
  me: OpsMember;
  onCreated: () => Promise<void>;
}) {
  const others = members.filter((m) => m.email !== me.email);
  const [kind, setKind] = useState<ItemKind>("design_concept");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [reviewer, setReviewer] = useState(others[0]?.email ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      await createItem({
        kind,
        title,
        body,
        reviewer_email: reviewer || null,
      });
      setTitle("");
      setBody("");
      await onCreated();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="bg-face-100">
      <h2 className="font-display text-lg">Send something for review</h2>
      {error !== null && (
        <p className="mt-2 rounded-lg border-[1.5px] border-black bg-accent-50 px-3 py-2 text-xs font-bold text-accent-700">
          {error}
        </p>
      )}
      <form
        className="mt-3 flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ops-kind" className="text-sm font-bold">
              What is it?
            </label>
            <select
              id="ops-kind"
              value={kind}
              onChange={(event) => setKind(event.target.value as ItemKind)}
              className="min-h-11 rounded-xl border-2 border-black bg-white px-3 text-sm"
            >
              {ITEM_KINDS.map((k) => (
                <option key={k} value={k}>
                  {KIND_LABELS[k]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ops-reviewer" className="text-sm font-bold">
              Who should review it?
            </label>
            <select
              id="ops-reviewer"
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              className="min-h-11 rounded-xl border-2 border-black bg-white px-3 text-sm"
            >
              {others.map((m) => (
                <option key={m.email} value={m.email}>
                  {m.display_name} ({m.email})
                </option>
              ))}
              <option value="">No one — just save it</option>
            </select>
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="ops-title" className="text-sm font-bold">
            Title
          </label>
          <input
            id="ops-title"
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. New look for the case page"
            className="min-h-11 rounded-xl border-2 border-black bg-white px-4 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="ops-body" className="text-sm font-bold">
            Describe it
          </label>
          <textarea
            id="ops-body"
            rows={4}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder="Plain words are perfect — links welcome."
            className="rounded-xl border-2 border-black bg-white px-4 py-3 text-sm"
          />
        </div>
        <div>
          <Button type="submit" disabled={busy}>
            {busy ? "Sending…" : "Send it"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function TeamTab({
  members,
  me,
  onChanged,
}: {
  members: OpsMember[];
  me: OpsMember;
  onChanged: () => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      await addMember({ email, display_name: name });
      setEmail("");
      setName("");
      await onChanged();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-3">
        {members.map((member) => (
          <li key={member.id}>
            <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <p className="text-sm font-bold">{member.display_name}</p>
                <p className="text-xs text-ink-600">{member.email}</p>
              </div>
              <span className="rounded-full border-[1.5px] border-black bg-face-100 px-2.5 py-0.5 text-xs font-bold text-ink-600">
                {member.role}
              </span>
            </Card>
          </li>
        ))}
      </ul>
      {me.role === "owner" && (
        <Card className="bg-face-100">
          <h2 className="font-display text-lg">Add a teammate</h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-600">
            They sign in with the normal Sign up button using this email, and
            the council unlocks for them automatically.
          </p>
          {error !== null && (
            <p className="mt-2 rounded-lg border-[1.5px] border-black bg-accent-50 px-3 py-2 text-xs font-bold text-accent-700">
              {error}
            </p>
          )}
          <form
            className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <div className="flex flex-1 flex-col gap-1.5">
              <label htmlFor="member-name" className="text-sm font-bold">
                Name
              </label>
              <input
                id="member-name"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="min-h-11 rounded-xl border-2 border-black bg-white px-4 text-sm"
              />
            </div>
            <div className="flex flex-1 flex-col gap-1.5">
              <label htmlFor="member-email" className="text-sm font-bold">
                Email
              </label>
              <input
                id="member-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="min-h-11 rounded-xl border-2 border-black bg-white px-4 text-sm"
              />
            </div>
            <Button type="submit" disabled={busy}>
              {busy ? "Adding…" : "Add"}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}

export function OpsConsole() {
  const [me, setMe] = useState<OpsMember | null>(null);
  const [gateError, setGateError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("inbox");
  const [items, setItems] = useState<OpsItem[] | null>(null);
  const [members, setMembers] = useState<OpsMember[]>([]);
  const [researching, setResearching] = useState(false);
  const [researchNote, setResearchNote] = useState<string | null>(null);

  const refetch = useCallback(async (activeTab: Tab) => {
    if (activeTab === "team") return;
    const box = activeTab === "inbox" ? "inbox" : activeTab === "research" ? "research" : "all";
    setItems(await listItems(box));
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await seed(); // idempotent; dev only
        const who = await getMe();
        if (cancelled) return;
        setMe(who);
        setMembers(await listMembers());
        await refetch("inbox");
      } catch (err) {
        if (!cancelled) setGateError(describeError(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refetch]);

  useEffect(() => {
    if (me !== null) void refetch(tab);
  }, [tab, me, refetch]);

  async function handleResearch() {
    setResearching(true);
    setResearchNote(null);
    try {
      const counts = await runResearch();
      setResearchNote(
        `Research done — ${counts.created} new brief${counts.created === 1 ? "" : "s"}.`,
      );
      await refetch(tab);
    } catch (err) {
      setResearchNote(`Research failed: ${describeError(err)}`);
    } finally {
      setResearching(false);
    }
  }

  if (gateError !== null) {
    return (
      <Card className="bg-face-100">
        <h2 className="font-display text-lg">This area is for the team</h2>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-600">
          {gateError}
        </p>
      </Card>
    );
  }

  if (me === null) {
    return <p className="text-sm text-ink-400">Loading the council…</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Ops sections" className="flex flex-wrap gap-2">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`min-h-11 rounded-xl border-2 border-black px-4 text-sm font-bold transition-colors ${
              tab === key ? "bg-black text-white" : "bg-white hover:bg-face-100"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "team" ? (
        <TeamTab
          members={members}
          me={me}
          onChanged={async () => setMembers(await listMembers())}
        />
      ) : (
        <>
          {tab === "research" && (
            <div className="flex flex-wrap items-center gap-3">
              <Button disabled={researching} onClick={() => void handleResearch()}>
                {researching ? "Karen is researching…" : "Run research now"}
              </Button>
              {researchNote !== null && (
                <span className="text-xs font-bold text-ink-600">
                  {researchNote}
                </span>
              )}
            </div>
          )}
          {tab !== "research" && (
            <NewItemForm
              members={members}
              me={me}
              onCreated={async () => refetch(tab)}
            />
          )}
          {items === null ? (
            <p className="text-sm text-ink-400">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-ink-400">
              {tab === "inbox"
                ? "Nothing waiting on you. Enjoy it while it lasts."
                : tab === "research"
                  ? "No research briefs yet — run research to get the first batch."
                  : "Nothing here yet."}
            </p>
          ) : (
            <ul className="flex flex-col gap-4">
              {items.map((item) => (
                <li key={item.id}>
                  <ItemRow item={item} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

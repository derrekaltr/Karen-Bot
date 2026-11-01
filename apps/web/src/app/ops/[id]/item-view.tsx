"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ApiError } from "@/lib/api";
import {
  addComment,
  approveItem,
  getItem,
  getMe,
  requestChanges,
  resubmitItem,
  type OpsItemDetail,
  type OpsMember,
} from "@/lib/ops-api";
import { KindPill, StatusPill } from "../badges";

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Could not reach the KarenBot API.";
}

export function OpsItemView({ itemId }: { itemId: string }) {
  const [item, setItem] = useState<OpsItemDetail | null>(null);
  const [me, setMe] = useState<OpsMember | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const refetch = useCallback(async () => {
    setItem(await getItem(itemId));
  }, [itemId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [who] = await Promise.all([getMe()]);
        if (cancelled) return;
        setMe(who);
        await refetch();
      } catch (err) {
        if (!cancelled) setError(describeError(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refetch]);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    setBusy(true);
    try {
      await action();
      setComment("");
      await refetch();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  if (error !== null && item === null) {
    return (
      <p className="rounded-xl border-2 border-black bg-accent-50 px-4 py-3 text-sm font-bold text-accent-700">
        Could not load this item: {error}
      </p>
    );
  }

  if (item === null || me === null) {
    return <p className="text-sm text-ink-400">Loading…</p>;
  }

  const isReviewer = item.reviewer_email === me.email;
  const isSubmitter = item.created_by_email === me.email;
  const decidable =
    isReviewer && ["in_review", "changes_requested"].includes(item.status);

  return (
    <article>
      <div className="flex flex-wrap items-center gap-2">
        <KindPill kind={item.kind} />
        <StatusPill status={item.status} />
      </div>
      <h1 className="mt-2 font-display text-3xl leading-tight tracking-tight">
        {item.title}
      </h1>
      <p className="mt-1 text-xs text-ink-400">
        From {item.created_by_email}
        {item.reviewer_email !== null
          ? ` — for ${item.reviewer_email} to review`
          : ""}{" "}
        — {new Date(item.created_at).toLocaleString()}
      </p>

      <p className="mt-5 text-sm leading-relaxed whitespace-pre-wrap">
        {item.body}
      </p>

      {item.recommendation !== null && (
        <div className="mt-5 rounded-2xl border-2 border-black bg-money-100 p-5">
          <h2 className="font-display text-base">Karen&apos;s recommendation</h2>
          <p className="mt-1 text-sm leading-relaxed">{item.recommendation}</p>
        </div>
      )}

      {item.source_urls.length > 0 && (
        <section className="mt-5">
          <h2 className="text-sm font-bold">Sources</h2>
          <ul className="mt-1 flex flex-col gap-1">
            {item.source_urls.map((url) => (
              <li key={url}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm break-all text-accent-600 underline"
                >
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {error !== null && (
        <p
          role="alert"
          className="mt-5 rounded-xl border-2 border-black bg-accent-50 px-4 py-3 text-sm font-bold text-accent-700"
        >
          {error}
        </p>
      )}

      {/* Comments */}
      <section className="mt-8" aria-label="Comments">
        <h2 className="font-display text-lg">Discussion</h2>
        <ul className="mt-3 flex flex-col gap-3">
          {item.comments.map((c) => (
            <li key={c.id}>
              <Card className="p-4">
                <p className="text-xs font-bold text-ink-400">
                  {c.author_email} — {new Date(c.created_at).toLocaleString()}
                </p>
                <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap">
                  {c.body}
                </p>
              </Card>
            </li>
          ))}
          {item.comments.length === 0 && (
            <li className="text-sm text-ink-400">No comments yet.</li>
          )}
        </ul>
        <form
          className="mt-4 flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (comment.trim()) void run(() => addComment(itemId, comment));
          }}
        >
          <textarea
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder={
              decidable
                ? "Say what should change, or leave a note with your approval…"
                : "Add a comment…"
            }
            aria-label="Comment"
            className="rounded-xl border-2 border-black bg-white px-4 py-3 text-sm"
          />
          <div className="flex flex-wrap gap-3">
            {decidable ? (
              <>
                <Button
                  disabled={busy}
                  onClick={() =>
                    void run(() => approveItem(itemId, comment || null))
                  }
                >
                  Approve
                </Button>
                <Button
                  variant="danger"
                  disabled={busy}
                  onClick={() =>
                    void run(() => requestChanges(itemId, comment || null))
                  }
                >
                  Request changes
                </Button>
              </>
            ) : (
              <Button type="submit" variant="secondary" disabled={busy}>
                Comment
              </Button>
            )}
            {decidable && (
              <Button type="submit" variant="secondary" disabled={busy}>
                Just comment
              </Button>
            )}
            {isSubmitter && item.status === "changes_requested" && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => void run(() => resubmitItem(itemId))}
              >
                Send back for review
              </Button>
            )}
          </div>
        </form>
      </section>
    </article>
  );
}

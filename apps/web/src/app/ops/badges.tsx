import type { ItemKind, ItemStatus } from "@/lib/ops-api";
import { KIND_LABELS } from "@/lib/ops-api";

const STATUS_STYLES: Record<ItemStatus, { label: string; classes: string }> = {
  new: { label: "New", classes: "bg-face-100 text-ink-600" },
  in_review: { label: "Waiting for review", classes: "bg-bob-100 text-ink-900" },
  approved: { label: "Approved", classes: "bg-money-100 text-money-700" },
  changes_requested: {
    label: "Changes requested",
    classes: "bg-accent-100 text-accent-700",
  },
  archived: { label: "Archived", classes: "bg-face-100 text-ink-400" },
};

export function StatusPill({ status }: { status: ItemStatus }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.new;
  return (
    <span
      className={`rounded-full border-[1.5px] border-black px-2.5 py-0.5 text-xs font-bold ${style.classes}`}
    >
      {style.label}
    </span>
  );
}

export function KindPill({ kind }: { kind: ItemKind }) {
  return (
    <span className="rounded-full border-[1.5px] border-black bg-white px-2.5 py-0.5 text-xs font-bold text-ink-600">
      {KIND_LABELS[kind] ?? kind}
    </span>
  );
}

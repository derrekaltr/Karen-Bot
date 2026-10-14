import {
  humanize,
  statusTone,
  type CaseStatus,
  type StatusTone,
} from "@/lib/api";

const toneClasses: Record<StatusTone, string> = {
  green: "bg-accent-100 text-accent-700",
  amber: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-700",
  neutral: "bg-slate-100 text-ink-600",
};

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${toneClasses[statusTone(status)]}`}
    >
      {humanize(status)}
    </span>
  );
}

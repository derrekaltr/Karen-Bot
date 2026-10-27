import {
  humanize,
  statusTone,
  type CaseStatus,
  type StatusTone,
} from "@/lib/api";

const toneClasses: Record<StatusTone, string> = {
  green: "bg-money-100 text-money-700",
  amber: "bg-bob-100 text-ink-900",
  red: "bg-accent-100 text-accent-700",
  neutral: "bg-face-100 text-ink-600",
};

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border-[1.5px] border-black px-2.5 py-1 text-xs font-bold ${toneClasses[statusTone(status)]}`}
    >
      {humanize(status)}
    </span>
  );
}

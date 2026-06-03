import type { ReactNode } from "react";

export type MetricTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "muted";

interface MetricTileProps {
  label: ReactNode;
  value: ReactNode;
  /** Small caption rendered to the right of the value (e.g. "/ 2.00"). */
  suffix?: ReactNode;
  /** Optional caption rendered under the value (e.g. percentage). */
  hint?: ReactNode;
  tone?: MetricTone;
  /** Optional icon shown above the label (lucide-react component). */
  icon?: ReactNode;
}

/**
 * Phase 6.0.A — compact metric tile.
 *
 * Replaces the inline metric blocks duplicated across StatsCards,
 * EvaluationPage's ScoreSummary and SyllabusViewer's metadata
 * strip. The tone palette is the design-system semantic set:
 *
 *   - success : emerald   (completed, OK, "valutati 9/9")
 *   - warning : amber     (partial, gap, "NA 1")
 *   - danger  : rose      (failed, error)
 *   - info    : cyan      (running, navigation)
 *   - neutral : slate     (pending, idle)
 *   - muted   : card      (neutral count, non-status)
 */
const toneStyles: Record<MetricTone, { border: string; bg: string; value: string }> = {
  success: {
    border: "border-emerald-200 dark:border-emerald-500/30",
    bg: "bg-emerald-500/10",
    value: "text-emerald-800 dark:text-emerald-300",
  },
  warning: {
    border: "border-amber-200 dark:border-amber-500/30",
    bg: "bg-amber-500/10",
    value: "text-amber-800 dark:text-amber-300",
  },
  danger: {
    border: "border-rose-200 dark:border-rose-500/30",
    bg: "bg-rose-500/10",
    value: "text-rose-800 dark:text-rose-300",
  },
  info: {
    border: "border-cyan-200 dark:border-cyan-500/30",
    bg: "bg-cyan-500/10",
    value: "text-cyan-800 dark:text-cyan-300",
  },
  neutral: {
    border: "border-slate-200 dark:border-slate-500/30",
    bg: "bg-slate-500/10",
    value: "text-slate-800 dark:text-slate-300",
  },
  muted: {
    border: "border-border",
    bg: "bg-card",
    value: "text-foreground",
  },
};

export function MetricTile({
  label,
  value,
  suffix,
  hint,
  tone = "muted",
  icon,
}: MetricTileProps) {
  const s = toneStyles[tone];
  return (
    <div
      className={`min-w-[96px] rounded-md border px-3 py-2 ${s.border} ${s.bg}`}
    >
      <div className="flex items-center gap-1.5">
        {icon ? (
          <span className="text-muted-foreground" aria-hidden>
            {icon}
          </span>
        ) : null}
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
      </div>
      <p
        className={`mt-1 text-xl font-semibold leading-none tabular-nums ${s.value}`}
      >
        {value}
        {suffix ? (
          <span className="ml-1 text-[10px] font-normal text-muted-foreground">
            {suffix}
          </span>
        ) : null}
      </p>
      {hint ? (
        <p className="mt-1 text-[10px] text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

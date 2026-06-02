import { Badge } from "@/components/ui/badge";
import type { EvaluationStatus } from "@/lib/types";

interface Props {
  status: EvaluationStatus;
  /** When true (default false) shows a pulsing dot for the `running` state. */
  animate?: boolean;
}

/**
 * Phase 5.9.D — single source of truth for evaluation-status badges.
 *
 * Palette aligned to the design charter:
 *   - completed   emerald
 *   - partial     amber
 *   - failed      rose
 *   - running     cyan
 *   - pending     slate
 *
 * Use this component everywhere a status pill is rendered (the
 * `SyllabusViewer` history list, the `EvaluationPage` header, any
 * future history/results page). The inline copies previously duplicated
 * across pages have been removed.
 */
export function StatusBadge({ status, animate = false }: Props) {
  const config: Record<
    EvaluationStatus,
    {
      label: string;
      variant: "default" | "secondary" | "destructive" | "outline";
      extra?: string;
    }
  > = {
    pending: {
      label: "in attesa",
      variant: "outline",
      extra:
        "border-slate-300 bg-slate-500/10 text-slate-700 dark:border-slate-600 dark:text-slate-300",
    },
    running: {
      label: "in esecuzione",
      variant: "outline",
      extra:
        "border-cyan-300 bg-cyan-500/10 text-cyan-800 dark:text-cyan-300" +
        (animate ? " animate-pulse" : ""),
    },
    completed: {
      label: "completata",
      variant: "outline",
      extra:
        "border-emerald-300 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
    },
    partial: {
      label: "parziale",
      variant: "outline",
      extra:
        "border-amber-300 bg-amber-500/10 text-amber-800 dark:text-amber-300",
    },
    failed: {
      label: "fallita",
      variant: "outline",
      extra:
        "border-rose-300 bg-rose-500/10 text-rose-800 dark:text-rose-300",
    },
  };
  const c = config[status];
  return (
    <Badge variant={c.variant} className={c.extra}>
      {c.label}
    </Badge>
  );
}

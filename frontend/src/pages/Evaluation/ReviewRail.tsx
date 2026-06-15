import { SyntheticVerdict } from "@/components/SyntheticVerdict";
import { CORE_CRITERIA } from "@/data/rubric";
import { focusCriteria } from "@/lib/events";
import type { EvaluationDetail } from "@/lib/types";

import { EvaluationSection } from "./EvaluationSection";

/**
 * Phase 10.A R2 — review rail (sticky right column on desktop).
 *
 * Scaffold scope: verdict + clickable "Priorità di revisione". Compact
 * E1-E5 summary and documents move here in a later commit; the full
 * extended analysis lives in the main column.
 */
export function ReviewRail({ data }: { data: EvaluationDetail }) {
  return (
    <div className="divide-y divide-slate-100">
      <EvaluationSection title="Sintesi della revisione">
        <SyntheticVerdict data={data} />
      </EvaluationSection>
      <PrioritaRevisione data={data} />
    </div>
  );
}

interface PriorityItem {
  code: string;
  name: string;
  score: number;
}

function PrioritaRevisione({ data }: { data: EvaluationDetail }) {
  const scores = data.criterion_scores ?? {};
  const items: PriorityItem[] = CORE_CRITERIA.flatMap((c) => {
    const score = scores[c.code];
    return score === 0 || score === 1
      ? [{ code: c.code, name: c.name, score }]
      : [];
  }).sort((a, b) => a.score - b.score); // criticità (0) before aree (1)

  return (
    <EvaluationSection title="Priorità di revisione">
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nessuna priorità: nessun criterio sotto la soglia.
        </p>
      ) : (
        <ul className="space-y-0.5">
          {items.map((it) => (
            <li key={it.code}>
              <button
                type="button"
                onClick={() => focusCriteria([it.code])}
                className="flex w-full items-center justify-between gap-2 rounded px-1.5 py-1 text-left text-sm hover:bg-muted/50"
              >
                <span className="min-w-0 truncate">
                  <span className="font-mono text-xs text-muted-foreground">
                    {it.code}
                  </span>{" "}
                  {it.name}
                </span>
                <span
                  className={
                    "shrink-0 text-xs " +
                    (it.score === 0 ? "text-rose-700" : "text-amber-700")
                  }
                >
                  {it.score === 0 ? "Criticità" : "Da migliorare"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </EvaluationSection>
  );
}

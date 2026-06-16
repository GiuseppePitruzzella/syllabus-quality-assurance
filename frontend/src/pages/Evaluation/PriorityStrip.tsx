import { reviewPriorities } from "@/lib/verdict";
import { CORE_CRITERIA } from "@/data/rubric";
import { focusCriteria } from "@/lib/events";
import type { EvaluationDetail } from "@/lib/types";

const NAME_BY_CODE = new Map(
  CORE_CRITERIA.map((c) => [c.code, c.name] as const),
);

/**
 * Phase 10.B — full-width "Priorità di revisione" strip (replaces the
 * rail's priorities). Lists criteria below threshold (0/1), criticità
 * first; clicking jumps to and expands the criterion in C1-C9.
 */
export function PriorityStrip({ data }: { data: EvaluationDetail }) {
  const priorities = reviewPriorities(data.criterion_scores);
  return (
    <section className="bg-amber-50/50 px-5 py-4 sm:px-7">
      <h2 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
        Priorità di revisione
      </h2>
      {priorities.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">
          Nessuna priorità: nessun criterio sotto la soglia.
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {priorities.map((p) => (
            <button
              key={p.code}
              type="button"
              onClick={() => focusCriteria([p.code])}
              className={
                "inline-flex items-center gap-2 rounded-md border bg-white px-3 py-2 text-left text-sm transition hover:shadow-sm " +
                (p.score === 0
                  ? "border-rose-200 hover:border-rose-300"
                  : "border-amber-200 hover:border-amber-300")
              }
            >
              <code className="font-mono text-[11px] font-semibold text-slate-400">
                {p.code}
              </code>
              <span className="text-slate-700">{NAME_BY_CODE.get(p.code)}</span>
              <span
                className={
                  "text-[10px] font-semibold uppercase " +
                  (p.score === 0 ? "text-rose-700" : "text-amber-700")
                }
              >
                {p.score === 0 ? "Criticità" : "Da migliorare"}
              </span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

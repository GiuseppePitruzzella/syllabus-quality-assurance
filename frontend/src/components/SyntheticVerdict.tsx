import { useState } from "react";
import { ChevronDown, ChevronUp, Info } from "lucide-react";

import { computeVerdict, type Verdict, type VerdictChip } from "@/lib/verdict";
import { CORE_CRITERIA } from "@/data/rubric";
import { useTechnicalView } from "@/context/technicalView";
import type { EvaluationDetail } from "@/lib/types";

const NAME_BY_CODE = new Map(
  CORE_CRITERIA.map((c) => [c.code, c.name] as const),
);

const TONE_STYLES: Record<Verdict["tone"], { container: string; headline: string }> = {
  positive: { container: "border-emerald-200 bg-emerald-50", headline: "text-emerald-900" },
  neutral: { container: "border-slate-200 bg-slate-50", headline: "text-slate-900" },
  attention: { container: "border-amber-300 bg-amber-50", headline: "text-amber-950" },
  muted: { container: "border-slate-200 bg-slate-50", headline: "text-slate-700" },
};

const CHIP_STYLES: Record<VerdictChip["tone"], string> = {
  critical: "border-rose-300 bg-rose-100 text-rose-800",
  warning: "border-amber-300 bg-amber-100 text-amber-800",
  muted: "border-slate-300 bg-slate-100 text-slate-700",
};

export function SyntheticVerdict({ data }: { data: EvaluationDetail }) {
  const { technical } = useTechnicalView();
  const [open, setOpen] = useState(false);

  const verdict = computeVerdict({
    status: data.status,
    coreScore: data.core_score,
    coverage: data.coverage,
    criterionScores: data.criterion_scores,
  });

  const tone = TONE_STYLES[verdict.tone];

  return (
    <section className={"rounded-xl border p-5 " + tone.container}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Verdetto sintetico
      </p>
      <h2 className={"mt-1 text-xl font-semibold " + tone.headline}>
        {verdict.headline}
      </h2>

      {verdict.chips.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {verdict.chips.map((chip, i) => (
            <span
              key={i}
              className={
                "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium " +
                CHIP_STYLES[chip.tone]
              }
            >
              {chip.label}
            </span>
          ))}
        </div>
      ) : null}

      <VerdictAnnotations
        verdict={verdict}
        technical={technical}
        receivedCoreScore={data.core_score}
      />

      {verdict.band !== "non_disponibile" ? (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            Perché questo verdetto?
            {open ? (
              <ChevronUp className="h-4 w-4" aria-hidden />
            ) : (
              <ChevronDown className="h-4 w-4" aria-hidden />
            )}
          </button>
          {open ? <VerdictExplanation data={data} /> : null}
        </div>
      ) : null}
    </section>
  );
}

function VerdictAnnotations({
  verdict,
  technical,
  receivedCoreScore,
}: {
  verdict: Verdict;
  technical: boolean;
  receivedCoreScore: number | null;
}) {
  const notes: string[] = [];
  if (verdict.partialExecution) {
    notes.push("Valutazione completata parzialmente.");
  }
  if (verdict.partialCoverage) {
    notes.push(
      `Valutazione parziale: ${verdict.naCount} ${
        verdict.naCount === 1
          ? "criterio non valutabile"
          : "criteri non valutabili"
      }.`,
    );
  }
  if (verdict.inconsistent) {
    notes.push(
      "Alcuni valori aggregati non coincidono con i punteggi per criterio; il verdetto usa i punteggi.",
    );
  }
  if (notes.length === 0) return null;

  return (
    <ul className="mt-3 space-y-1">
      {notes.map((n, i) => (
        <li
          key={i}
          className="flex items-start gap-1.5 text-xs text-muted-foreground"
        >
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>{n}</span>
        </li>
      ))}
      {technical && verdict.inconsistent ? (
        <li className="flex items-start gap-1.5 text-xs text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            CoreScore ricevuto {receivedCoreScore ?? "—"} · ricalcolato{" "}
            {verdict.computedCoreScore !== null
              ? verdict.computedCoreScore.toFixed(2)
              : "—"}
          </span>
        </li>
      ) : null}
    </ul>
  );
}

function VerdictExplanation({ data }: { data: EvaluationDetail }) {
  const scores = data.criterion_scores ?? {};
  const critical: string[] = [];
  const improvable: string[] = [];
  const na: string[] = [];

  for (const [code, name] of NAME_BY_CODE) {
    const raw = scores[code];
    if (raw === 0) critical.push(`${code} — ${name}`);
    else if (raw === 1) improvable.push(`${code} — ${name}`);
    else if (raw === undefined || raw === null) na.push(`${code} — ${name}`);
  }

  return (
    <div className="mt-2 space-y-2 text-sm">
      <p className="text-muted-foreground">
        Il verdetto deriva dai punteggi 0/1/2 dei nove criteri core; la media
        determina la qualità complessiva.
      </p>
      <ExplanationGroup title="Da correggere (criticità)" items={critical} />
      <ExplanationGroup title="Da migliorare" items={improvable} />
      <ExplanationGroup title="Non valutabili" items={na} />
    </div>
  );
}

function ExplanationGroup({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <ul className="mt-1 space-y-0.5">
        {items.map((it) => (
          <li key={it} className="text-sm">
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

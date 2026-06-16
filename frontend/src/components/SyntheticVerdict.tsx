import { useState } from "react";
import { ChevronDown, ChevronUp, Info, TriangleAlert } from "lucide-react";

import {
  computeVerdict,
  verdictSummarySentence,
  CORE_CRITERION_CODES,
  type Verdict,
} from "@/lib/verdict";
import { focusCriteria } from "@/lib/events";
import { useTechnicalView } from "@/context/technicalView";
import type { EvaluationDetail } from "@/lib/types";

const BAND_ACCENT: Record<Verdict["band"], string> = {
  ottima: "text-emerald-800",
  buona: "text-sky-800",
  discreta: "text-amber-800",
  da_rivedere: "text-rose-800",
  copertura_insufficiente: "text-amber-800",
  non_disponibile: "text-slate-700",
};

type ChipTone = "critical" | "improve" | "ok" | "neutral";

const CHIP_TONE: Record<ChipTone, string> = {
  critical: "bg-rose-100/70 text-rose-800",
  improve: "bg-amber-100/70 text-amber-800",
  ok: "bg-emerald-100/70 text-emerald-800",
  neutral: "bg-slate-100 text-slate-600",
};

function codesByScore(data: EvaluationDetail, target: number): string[] {
  const s = data.criterion_scores ?? {};
  return CORE_CRITERION_CODES.filter((c) => s[c] === target);
}

export function SyntheticVerdict({
  data,
  variant = "default",
}: {
  data: EvaluationDetail;
  variant?: "default" | "rail";
}) {
  const { technical } = useTechnicalView();
  const [open, setOpen] = useState(false);

  const verdict = computeVerdict({
    status: data.status,
    coreScore: data.core_score,
    coverage: data.coverage,
    criterionScores: data.criterion_scores,
  });

  const sentence = verdictSummarySentence(verdict);
  const showBody = verdict.band !== "non_disponibile";
  const isRail = variant === "rail";

  return (
    <section className={isRail ? "" : "bg-slate-100/65 px-5 py-6 sm:px-7"}>
      <h2
        className={
          (isRail ? "text-2xl" : "text-2xl sm:text-3xl") +
          " font-semibold leading-tight tracking-tight " +
          BAND_ACCENT[verdict.band]
        }
      >
        {verdict.headline}
      </h2>

      {sentence ? (
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
          {sentence}
        </p>
      ) : null}

      {showBody && !isRail ? <Chips data={data} verdict={verdict} /> : null}
      {showBody && isRail ? <RailCounts verdict={verdict} /> : null}

      <Annotations
        verdict={verdict}
        technical={technical}
        receivedCoreScore={data.core_score}
      />

      {sentence ? (
        <div className={isRail ? "mt-4" : "mt-4 border-t border-slate-200/70 pt-3"}>
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
          {open ? <WhyShort verdict={verdict} /> : null}
        </div>
      ) : null}
    </section>
  );
}

function RailCounts({ verdict }: { verdict: Verdict }) {
  return (
    <p className="mt-4 text-xs leading-relaxed text-slate-500">
      <strong className={verdict.criticalCount > 0 ? "text-rose-700" : "text-slate-700"}>
        {verdict.criticalCount} criticità
      </strong>
      {" · "}
      <strong className={verdict.improvableCount > 0 ? "text-amber-700" : "text-slate-700"}>
        {verdict.improvableCount} {verdict.improvableCount === 1 ? "area" : "aree"} da migliorare
      </strong>
      {" · "}
      {verdict.evaluatedCount}/{verdict.totalCount} valutati
    </p>
  );
}

function Chips({ data, verdict }: { data: EvaluationDetail; verdict: Verdict }) {
  return (
    <div className="mt-4 flex flex-col items-stretch gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      {verdict.criticalCount > 0 ? (
        <Chip
          label={`${verdict.criticalCount} criticità`}
          tone="critical"
          codes={codesByScore(data, 0)}
        />
      ) : (
        <Chip label="0 criticità" tone="ok" />
      )}

      {verdict.improvableCount > 0 ? (
        <Chip
          label={
            verdict.improvableCount === 1
              ? "1 area da migliorare"
              : `${verdict.improvableCount} aree da migliorare`
          }
          tone="improve"
          codes={codesByScore(data, 1)}
        />
      ) : null}

      <Chip
        label={`${verdict.evaluatedCount}/${verdict.totalCount} criteri valutati`}
        tone="neutral"
      />
    </div>
  );
}

function Chip({
  label,
  tone,
  codes,
}: {
  label: string;
  tone: ChipTone;
  codes?: string[];
}) {
  const cls =
    "inline-flex items-center justify-center px-2.5 py-1 text-xs font-medium " +
    CHIP_TONE[tone];
  if (codes && codes.length > 0) {
    return (
      <button
        type="button"
        onClick={() => focusCriteria(codes)}
        title="Vai ai criteri interessati"
        className={cls + " cursor-pointer transition hover:brightness-95"}
      >
        {label}
      </button>
    );
  }
  return <span className={cls}>{label}</span>;
}

function Annotations({
  verdict,
  technical,
  receivedCoreScore,
}: {
  verdict: Verdict;
  technical: boolean;
  receivedCoreScore: number | null;
}) {
  const notes: string[] = [];

  if (verdict.band === "copertura_insufficiente") {
    notes.push(
      `Sono stati valutati ${verdict.evaluatedCount} criteri su ${verdict.totalCount}: copertura insufficiente per un giudizio complessivo.`,
    );
  } else if (verdict.partialCoverage) {
    notes.push(
      `Verdetto formulato su ${verdict.evaluatedCount} criteri valutabili su ${verdict.totalCount}.`,
    );
  }
  if (verdict.partialExecution) {
    notes.push(
      "La valutazione è stata completata parzialmente; alcuni controlli tecnici non sono terminati.",
    );
  }

  if (notes.length === 0 && !verdict.inconsistent) return null;

  return (
    <div className="mt-3 space-y-1.5">
      {notes.map((n, i) => (
        <p
          key={i}
          className="flex items-start gap-1.5 text-xs text-slate-500"
        >
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>{n}</span>
        </p>
      ))}
      {verdict.inconsistent ? (
        <p className="flex items-start gap-1.5 text-xs text-rose-700">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            Alcuni valori aggregati non coincidono con i punteggi per criterio;
            il verdetto usa i punteggi.
            {technical ? (
              <>
                {" "}
                CoreScore ricevuto {receivedCoreScore ?? "—"} · ricalcolato{" "}
                {verdict.computedCoreScore !== null
                  ? verdict.computedCoreScore.toFixed(2)
                  : "—"}
                .
              </>
            ) : null}
          </span>
        </p>
      ) : null}
    </div>
  );
}

function WhyShort({ verdict }: { verdict: Verdict }) {
  const avg =
    verdict.computedCoreScore !== null
      ? verdict.computedCoreScore.toFixed(2)
      : "—";
  return (
    <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
      Il verdetto deriva dai punteggi 0/1/2 dei nove criteri core: la loro media
      determina la qualità complessiva ({avg}/2). Le criticità e le aree da
      migliorare sono evidenziate nei criteri qui sotto — espandi un criterio
      per la motivazione e le citazioni dal syllabus.
    </p>
  );
}

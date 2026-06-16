import type { ReactNode } from "react";

import { SyntheticVerdict } from "@/components/SyntheticVerdict";
import { CORE_CRITERIA, EXTENDED_CRITERIA } from "@/data/rubric";
import { focusCriteria } from "@/lib/events";
import type { EvaluationDetail } from "@/lib/types";

/**
 * Phase 10.A R2 — review rail (sticky right column on desktop).
 *
 * Verdict, actionable priorities and compact summaries stay visible
 * while the reader moves through the full review in the main column.
 */
export function ReviewRail({ data }: { data: EvaluationDetail }) {
  return (
    <div className="space-y-8">
      <RailSection title="Sintesi della revisione">
        <SyntheticVerdict data={data} variant="rail" />
      </RailSection>
      <PrioritaRevisione data={data} />
      <ExtendedSummary data={data} />
      <DocumentsSummary data={data} />
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
    <RailSection title="Priorità di revisione">
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nessuna priorità: nessun criterio sotto la soglia.
        </p>
      ) : (
        <ul className="divide-y divide-slate-200/70">
          {items.map((it) => (
            <li key={it.code}>
              <button
                type="button"
                onClick={() => focusCriteria([it.code])}
                className="flex w-full items-start justify-between gap-3 py-3 text-left text-sm hover:text-slate-950"
              >
                <span className="min-w-0">
                  <span className="mr-1.5 font-mono text-[10px] font-semibold text-slate-400">
                    {it.code}
                  </span>
                  <span className="text-slate-700">{it.name}</span>
                </span>
                <span
                  className={
                    "shrink-0 text-[10px] font-semibold uppercase " +
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
    </RailSection>
  );
}

function ExtendedSummary({ data }: { data: EvaluationDetail }) {
  const result = data.extended_criteria_result;
  if (!result) return null;
  const naByCode = new Map<string, (typeof result.na_criteria)[number]>(
    result.na_criteria.map((item) => [item.criterion_code, item]),
  );
  return (
    <RailSection
      title="Analisi estesa"
      action={
        <button
          type="button"
          onClick={() =>
            document.getElementById("extended-analysis")?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            })
          }
          className="text-[11px] font-medium text-slate-500 hover:text-slate-950"
        >
          Approfondisci
        </button>
      }
    >
      <p className="mb-3 text-xs leading-relaxed text-slate-500">
        Informazioni aggiuntive, separate dal CoreScore.
      </p>
      <ul className="space-y-2">
        {EXTENDED_CRITERIA.map((criterion) => {
          const score = result.criterion_scores[criterion.code];
          const na = naByCode.get(criterion.code);
          return (
            <li
              key={criterion.code}
              className="flex items-baseline justify-between gap-3 text-xs"
            >
              <span className="min-w-0 truncate text-slate-600">
                <code className="mr-1 font-mono text-[10px] text-slate-400">{criterion.code}</code>
                {criterion.name}
              </span>
              <span
                className={
                  typeof score === "number"
                    ? "font-semibold text-slate-700"
                    : "text-slate-400"
                }
              >
                {typeof score === "number"
                  ? score
                  : na?.source === "handler_error"
                    ? "errore"
                    : "NA"}
              </span>
            </li>
          );
        })}
      </ul>
    </RailSection>
  );
}

function DocumentsSummary({ data }: { data: EvaluationDetail }) {
  const docs = data.external_documents_used ?? [];
  if (docs.length === 0) return null;
  return (
    <RailSection title="Fonti aggiuntive">
      <ul className="space-y-3">
        {docs.map((doc, index) => (
          <li key={`${doc.criterion_code}-${doc.local_document_id}-${index}`}>
            <p className="text-xs font-medium text-slate-700">
              <code className="mr-1 font-mono text-[10px] text-slate-400">
                {doc.criterion_code}
              </code>
              {doc.title ?? `Documento ${doc.local_document_id}`}
            </p>
            <p className="mt-0.5 text-[10px] text-slate-400">
              {doc.resolution_reason === "explicit_selection"
                ? "Selezione esplicita"
                : doc.resolution_reason === "academic_year_match"
                  ? "Anno accademico"
                  : "Ultima versione disponibile"}
            </p>
          </li>
        ))}
      </ul>
    </RailSection>
  );
}

function RailSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

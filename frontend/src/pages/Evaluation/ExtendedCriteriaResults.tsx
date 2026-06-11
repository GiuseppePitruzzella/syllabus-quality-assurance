import { useState } from "react";
import { AlertTriangle, ChevronRight, Info } from "lucide-react";

import { Section } from "@/components/layout/Section";
import type {
  EvaluationDetail,
  ExtendedCriteriaResultPayload,
  ExtendedCriterionCode,
  ExtendedJudgmentPayload,
  ExtendedNAPayload,
} from "@/lib/types";

interface Props {
  data: EvaluationDetail;
}

/**
 * Phase 9.D.2 — Extended criteria panel (E1-E5).
 *
 * Renders the A5 ExternalConsistencyAgent results in a section
 * deliberately distinct from the C1-C9 score panel. Two
 * methodological invariants drive every visual choice:
 *
 *   1. **E1-E5 do NOT contribute to the CoreScore.** A persistent
 *      "Non concorre al CoreScore" pill is shown next to the
 *      section title; the layout never mixes E-scores with the
 *      core panel.
 *
 *   2. **Technical NA and semantic NA are NOT equivalent.** A
 *      ``handler_error`` (technical NA from the coordinator) is
 *      rendered with a prominent rose alert. ``resolver`` /
 *      ``handler_na`` (semantic NA) is rendered with a discreet
 *      neutral pill — it's information about the criterion's
 *      applicability, not a pipeline failure.
 *
 * The compact row shows code / name / handler_version / score or
 * NA type. The expanded row reveals justification + evidences
 * (Phase 9.D.3 will polish the evidence rendering and add the
 * documents table).
 */
export function ExtendedCriteriaResults({ data }: Props) {
  // Hooks first — the early returns below are after this so we
  // don't violate the rules of hooks when the run is legacy.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const ext = data.extended_criteria_result;

  // Legacy run: the column was added in Phase 9.C.5.3, runs
  // produced before that have it null and we honour the distinct
  // EmptyState rather than rendering an empty table.
  if (ext === null || ext === undefined) {
    return <ExtendedCriteriaLegacyEmptyState />;
  }

  const judgmentByCode = new Map<string, ExtendedJudgmentPayload>(
    ext.judgments.map((j) => [j.criterion_code, j]),
  );
  const naByCode = new Map<string, ExtendedNAPayload>(
    ext.na_criteria.map((n) => [n.criterion_code, n]),
  );
  const handlerErrorCodes = new Set<string>(
    ext.na_criteria
      .filter((n) => n.source === "handler_error")
      .map((n) => n.criterion_code),
  );

  const toggle = (code: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  const expandAll = () =>
    setExpanded(new Set(EXTENDED_ORDER.map((c) => c.code)));
  const collapseAll = () => setExpanded(new Set());
  const anyExpanded = expanded.size > 0;

  return (
    <Section
      title="Criteri estesi E1-E5"
      headerAside={
        <div className="flex items-center gap-2">
          <NotInCoreScorePill />
          <button
            type="button"
            onClick={anyExpanded ? collapseAll : expandAll}
            className="text-xs font-medium text-primary hover:underline"
          >
            {anyExpanded ? "Comprimi tutto" : "Espandi tutto"}
          </button>
        </div>
      }
    >
      <ExtendedStatusBanner result={ext} />

      <div className="overflow-hidden rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="w-8 px-2 py-2" aria-hidden />
              <th className="w-14 px-3 py-2 text-left font-medium">Crit</th>
              <th className="px-3 py-2 text-left font-medium">Criterio</th>
              <th className="w-24 px-3 py-2 text-left font-medium">
                Handler ver.
              </th>
              <th className="w-32 px-3 py-2 text-right font-medium">
                Score / NA
              </th>
            </tr>
          </thead>
          <tbody>
            {EXTENDED_ORDER.map((c) => {
              const judgment = judgmentByCode.get(c.code) ?? null;
              const na = naByCode.get(c.code) ?? null;
              const promptVersion =
                ext.handler_prompt_versions[c.code] ?? null;
              const isExpanded = expanded.has(c.code);
              return (
                <ExtendedRow
                  key={c.code}
                  code={c.code}
                  name={c.name}
                  judgment={judgment}
                  na={na}
                  handlerVersion={promptVersion}
                  expanded={isExpanded}
                  onToggle={() => toggle(c.code)}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {handlerErrorCodes.size > 0 ? (
        <HandlerErrorsBanner errors={ext.handler_errors} />
      ) : null}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

interface ExtendedCriterionMeta {
  code: ExtendedCriterionCode;
  name: string;
}

/** Canonical evaluation order, kept aligned with rubric.ts. */
const EXTENDED_ORDER: ExtendedCriterionMeta[] = [
  { code: "E1", name: "Allineamento con SUA-CdS" },
  { code: "E2", name: "Allineamento con Matrice di Tuning" },
  { code: "E3", name: "Coerenza con Regolamento didattico" },
  { code: "E4", name: "Coerenza cross-lingua" },
  { code: "E5", name: "Aderenza agli usi dipartimentali / di CdL" },
];

function ExtendedRow({
  code,
  name,
  judgment,
  na,
  handlerVersion,
  expanded,
  onToggle,
}: {
  code: string;
  name: string;
  judgment: ExtendedJudgmentPayload | null;
  na: ExtendedNAPayload | null;
  handlerVersion: string | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isTechnicalNa = na?.source === "handler_error";
  return (
    <>
      <tr
        className={
          "cursor-pointer border-t transition-colors hover:bg-muted/30 " +
          (isTechnicalNa ? "bg-rose-500/[0.04]" : "")
        }
        onClick={onToggle}
      >
        <td className="px-2 py-2 text-muted-foreground">
          <ChevronRight
            className={
              "h-4 w-4 transition-transform " + (expanded ? "rotate-90" : "")
            }
            aria-hidden
          />
        </td>
        <td className="px-3 py-2 font-mono text-xs">{code}</td>
        <td className="px-3 py-2">{name}</td>
        <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">
          {handlerVersion ?? "—"}
        </td>
        <td className="px-3 py-2 text-right">
          <ExtendedOutcomeBadge judgment={judgment} na={na} />
        </td>
      </tr>
      {expanded ? (
        <tr className="border-t bg-muted/20">
          <td colSpan={5} className="px-6 py-3 text-sm">
            <ExpandedExtendedDetails judgment={judgment} na={na} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function ExpandedExtendedDetails({
  judgment,
  na,
}: {
  judgment: ExtendedJudgmentPayload | null;
  na: ExtendedNAPayload | null;
}) {
  // Technical NA (handler_error) takes priority: render the
  // handler's error message as a prominent rose block. The judgment
  // object may still be present (the coordinator synthesises a
  // technical-NA judgment in that case) but its body is generic, so
  // we lead with the error message.
  if (na?.source === "handler_error") {
    return (
      <div className="space-y-2">
        <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-xs text-rose-800 dark:text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="font-medium uppercase tracking-wide">
              Errore tecnico handler
            </p>
            <p className="text-rose-900/90 dark:text-rose-100/90">
              {na.reason}
            </p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Il criterio è stato marcato NA tecnico dal coordinator. Gli altri
          handler hanno potuto completare normalmente.
        </p>
      </div>
    );
  }

  // Semantic NA from resolver or handler: discreet body.
  if (na && (na.source === "resolver" || na.source === "handler_na")) {
    const label =
      na.source === "resolver"
        ? "NA dal resolver (documento non disponibile)"
        : "NA semantico dall'handler";
    return (
      <div className="space-y-2">
        <div className="flex items-start gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-900/80 dark:text-amber-200/80">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="font-medium uppercase tracking-wide">{label}</p>
            <p>{na.reason}</p>
          </div>
        </div>
        {judgment?.justification ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {judgment.justification}
          </p>
        ) : null}
      </div>
    );
  }

  if (!judgment) {
    return (
      <p className="text-xs text-muted-foreground">
        Nessuna motivazione disponibile.
      </p>
    );
  }

  // Numeric judgment: justification + evidences.
  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Motivazione
        </p>
        <p className="text-sm leading-relaxed">{judgment.justification}</p>
      </div>

      {judgment.evidences.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Evidenze testuali
          </p>
          <ul className="space-y-1.5 text-xs">
            {judgment.evidences.map((ev, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <code className="self-start rounded bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  {ev.source_field ??
                    (ev.source_document_id
                      ? `doc:${ev.source_document_id}`
                      : "—")}
                </code>
                <span className="text-foreground/90">“{ev.text}”</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Nessuna evidenza letterale riportata.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Outcome badges and banners
// ---------------------------------------------------------------------------

function ExtendedOutcomeBadge({
  judgment,
  na,
}: {
  judgment: ExtendedJudgmentPayload | null;
  na: ExtendedNAPayload | null;
}) {
  if (na?.source === "handler_error") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-700 dark:text-rose-300">
        NA tecnico
      </span>
    );
  }
  if (na?.source === "resolver") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
        NA resolver
      </span>
    );
  }
  if (na?.source === "handler_na") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-amber-500/20 bg-amber-500/5 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:text-amber-200">
        NA semantico
      </span>
    );
  }
  const score = judgment?.score ?? null;
  let cls =
    "inline-flex h-6 w-9 items-center justify-center rounded-md border text-sm font-medium tabular-nums ";
  let label: string;
  if (score === 2) {
    cls +=
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    label = "2";
  } else if (score === 1) {
    cls +=
      "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
    label = "1";
  } else if (score === 0) {
    cls +=
      "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
    label = "0";
  } else {
    cls += "border-border bg-muted text-muted-foreground";
    label = "—";
  }
  return <span className={cls}>{label}</span>;
}

function NotInCoreScorePill() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[11px] font-medium text-violet-700 dark:text-violet-300"
      title="I criteri estesi E1-E5 sono mantenuti separati dal CoreScore: non concorrono alla media C1-C9."
    >
      Non concorre al CoreScore
    </span>
  );
}

function ExtendedStatusBanner({
  result,
}: {
  result: ExtendedCriteriaResultPayload;
}) {
  // Compact one-line summary above the table. Status / counts.
  const numeric = result.judgments.filter(
    (j) => j.is_na === false && j.score !== null,
  ).length;
  const semanticNa = result.na_criteria.filter(
    (n) => n.source === "resolver" || n.source === "handler_na",
  ).length;
  const technicalNa = result.na_criteria.filter(
    (n) => n.source === "handler_error",
  ).length;

  let statusCls =
    "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ";
  if (result.status === "completed") {
    statusCls +=
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  } else if (result.status === "partial") {
    statusCls +=
      "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  } else {
    statusCls +=
      "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span className={statusCls}>A5 · {result.status}</span>
      <span>·</span>
      <span>{numeric} numerici</span>
      <span>·</span>
      <span>{semanticNa} NA semantici</span>
      {technicalNa > 0 ? (
        <>
          <span>·</span>
          <span className="font-medium text-rose-700 dark:text-rose-300">
            {technicalNa} NA tecnici
          </span>
        </>
      ) : null}
    </div>
  );
}

function HandlerErrorsBanner({
  errors,
}: {
  errors: Record<string, string>;
}) {
  return (
    <div className="mt-4 rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-sm">
      <p className="mb-1 flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-rose-800 dark:text-rose-300">
        <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
        Handler A5 falliti
      </p>
      <ul className="space-y-0.5 text-xs text-rose-900/90 dark:text-rose-200/90">
        {Object.entries(errors).map(([code, message]) => (
          <li key={code}>
            <code className="font-mono">{code}</code>: {message}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyState for legacy runs
// ---------------------------------------------------------------------------

function ExtendedCriteriaLegacyEmptyState() {
  return (
    <Section
      title="Criteri estesi E1-E5"
      headerAside={<NotInCoreScorePill />}
    >
      <div className="flex items-start gap-3 rounded-md border border-dashed bg-muted/20 px-4 py-4">
        <Info
          className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground"
          aria-hidden
        />
        <div className="space-y-1.5">
          <p className="text-sm font-medium">
            Risultati estesi non disponibili
          </p>
          <p className="text-xs text-muted-foreground">
            Questa valutazione è stata eseguita prima dell'introduzione di A5
            (Phase 9.C) e non ha prodotto giudizi sui criteri estesi E1-E5.
            Le run successive popolano questa sezione automaticamente.
          </p>
        </div>
      </div>
    </Section>
  );
}

import { useState } from "react";
import { AlertTriangle, ChevronRight, Info } from "lucide-react";

import { useTechnicalView } from "@/context/technicalView";
import type {
  EvaluationDetail,
  ExtendedCriteriaResultPayload,
  ExtendedCriterionCode,
  ExtendedEvidencePayload,
  ExtendedJudgmentPayload,
  ExtendedNAPayload,
} from "@/lib/types";
import { EvaluationSection } from "./EvaluationSection";

// Truncate the inline evidence preview so the table row stays compact
// (Phase 9.D.3 evidence rule: distinguish syllabus / external without
// blowing up row height; user expands for the full quote).
const EVIDENCE_PREVIEW_CHARS = 140;

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
  const { technical } = useTechnicalView();

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
    <div id="extended-analysis" className="scroll-mt-24">
      <EvaluationSection
        title="Criteri estesi E1-E5"
        aside={
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

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[10px] uppercase tracking-wide text-slate-400">
              <tr>
                <th className="w-8 px-2 py-2" aria-hidden />
                <th className="w-14 px-3 py-2 text-left font-medium">Crit</th>
                <th className="px-3 py-2 text-left font-medium">Criterio</th>
                {technical ? (
                  <th className="w-24 px-3 py-2 text-left font-medium">
                    Handler ver.
                  </th>
                ) : null}
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
                    technical={technical}
                  />
                );
              })}
            </tbody>
          </table>
        </div>

        {technical && handlerErrorCodes.size > 0 ? (
          <HandlerErrorsBanner errors={ext.handler_errors} />
        ) : null}
      </EvaluationSection>
    </div>
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
  technical,
}: {
  code: string;
  name: string;
  judgment: ExtendedJudgmentPayload | null;
  na: ExtendedNAPayload | null;
  handlerVersion: string | null;
  expanded: boolean;
  onToggle: () => void;
  technical: boolean;
}) {
  const isTechnicalNa = na?.source === "handler_error";
  return (
    <>
      <tr
        className={
          "cursor-pointer border-t border-slate-200/80 transition-colors hover:bg-slate-50 " +
          (isTechnicalNa ? "bg-rose-500/[0.04]" : "")
        }
        onClick={onToggle}
      >
        <td className="px-2 py-2 text-slate-500">
          <ChevronRight
            className={
              "h-4 w-4 transition-transform " + (expanded ? "rotate-90" : "")
            }
            aria-hidden
          />
        </td>
        <td className="px-3 py-2 font-mono text-xs">{code}</td>
        <td className="px-3 py-2">{name}</td>
        {technical ? (
          <td className="px-3 py-2 font-mono text-[11px] text-slate-500">
            {handlerVersion ?? "—"}
          </td>
        ) : null}
        <td className="px-3 py-2 text-right">
          <ExtendedOutcomeBadge judgment={judgment} na={na} />
        </td>
      </tr>
      {expanded ? (
        <tr className="border-t border-slate-200/80 bg-slate-50/70">
          <td colSpan={technical ? 5 : 4} className="px-6 py-3 text-sm">
            <ExpandedExtendedDetails
              judgment={judgment}
              na={na}
              technical={technical}
            />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function ExpandedExtendedDetails({
  judgment,
  na,
  technical,
}: {
  judgment: ExtendedJudgmentPayload | null;
  na: ExtendedNAPayload | null;
  technical: boolean;
}) {
  // Technical NA (handler_error) takes priority: render the
  // handler's error message as a prominent rose block. The judgment
  // object may still be present (the coordinator synthesises a
  // technical-NA judgment in that case) but its body is generic, so
  // we lead with the error message. In guided view the raw reason
  // (stack traces / infrastructure) is redacted.
  if (na?.source === "handler_error") {
    return (
      <div className="space-y-2">
        <div className="flex items-start gap-2 bg-rose-50 px-3 py-2 text-xs text-rose-800 dark:text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="font-medium uppercase tracking-wide">
              Errore tecnico handler
            </p>
            <p className="text-rose-900/90 dark:text-rose-100/90">
              {technical
                ? na.reason
                : "Il criterio non è stato valutato per un problema tecnico. Passa alla Vista tecnica per i dettagli."}
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-500">
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
        <div className="flex items-start gap-2 bg-amber-50 px-3 py-2 text-xs text-amber-900/80 dark:text-amber-200/80">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="font-medium uppercase tracking-wide">{label}</p>
            <p>{na.reason}</p>
          </div>
        </div>
        {judgment?.justification ? (
          <p className="text-xs leading-relaxed text-slate-500">
            {judgment.justification}
          </p>
        ) : null}
      </div>
    );
  }

  if (!judgment) {
    return (
      <p className="text-xs text-slate-500">
        Nessuna motivazione disponibile.
      </p>
    );
  }

  // Numeric judgment: justification + evidences.
  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          Motivazione
        </p>
        <p className="text-sm leading-relaxed">{judgment.justification}</p>
      </div>

      {judgment.evidences.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
            Evidenze testuali
          </p>
          <ul className="space-y-1.5">
            {judgment.evidences.map((ev, i) => (
              <EvidenceRow key={i} evidence={ev} />
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-slate-500">
          Nessuna evidenza letterale riportata.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evidence row (Phase 9.D.3 polish)
// ---------------------------------------------------------------------------

/**
 * Compact evidence line with a leading pill that makes the source
 * explicit ("Syllabus · field" vs "Documento esterno · doc:N") and a
 * truncated quote. The user expands to read the full quote — long
 * Italian justifications would otherwise stretch the row well past
 * the table width.
 */
function EvidenceRow({ evidence }: { evidence: ExtendedEvidencePayload }) {
  const [expanded, setExpanded] = useState(false);
  const isSyllabus = evidence.source_field !== null;
  const isExternal = evidence.source_document_id !== null;
  const text = evidence.text ?? "";
  const isLong = text.length > EVIDENCE_PREVIEW_CHARS;
  const display = expanded || !isLong
    ? text
    : `${text.slice(0, EVIDENCE_PREVIEW_CHARS).trimEnd()}…`;

  // Pill content branches on the typed source. Order matters: the
  // E4 paired-prefix rule keeps source_field on both halves of a
  // pair, while E1/E2/E3/E5 numeric judgments must have at least
  // one external citation.
  let badgeCls =
    "inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ";
  let badgeText: string;
  let detail: string | null = null;
  if (isSyllabus) {
    badgeCls +=
      "bg-sky-500/10 text-sky-700 dark:text-sky-300";
    badgeText = "Syllabus";
    detail = evidence.source_field;
  } else if (isExternal) {
    badgeCls +=
      "bg-violet-500/10 text-violet-700 dark:text-violet-300";
    badgeText = "Documento esterno";
    detail = `doc:${evidence.source_document_id}${
      evidence.source_chunk_id ? ` · ${evidence.source_chunk_id}` : ""
    }`;
  } else {
    // Defensive: a well-formed payload always has exactly one
    // source; the API-side validator would have rejected the run
    // otherwise. We still render the row so debug remains possible.
    badgeCls += "bg-slate-100 text-slate-500";
    badgeText = "—";
  }

  return (
    <li className="bg-slate-50/80 px-2.5 py-2 text-xs">
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        <span className={badgeCls}>{badgeText}</span>
        {detail ? (
          <code className="bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
            {detail}
          </code>
        ) : null}
      </div>
      <p className="leading-relaxed text-foreground/90">
        <span className="text-slate-500">“</span>
        {display}
        <span className="text-slate-500">”</span>
        {isLong ? (
          <>
            {" "}
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-[11px] font-medium text-primary hover:underline"
            >
              {expanded ? "comprimi" : "espandi"}
            </button>
          </>
        ) : null}
      </p>
    </li>
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
      <span className="text-[11px] font-medium text-rose-700 dark:text-rose-300">
        NA tecnico
      </span>
    );
  }
  if (na?.source === "resolver") {
    return (
      <span className="text-[11px] font-medium text-slate-500">
        NA resolver
      </span>
    );
  }
  if (na?.source === "handler_na") {
    return (
      <span className="text-[11px] font-medium text-amber-800 dark:text-amber-200">
        NA semantico
      </span>
    );
  }
  const score = judgment?.score ?? null;
  let cls = "text-sm font-semibold tabular-nums ";
  let label: string;
  if (score === 2) {
    cls += "text-emerald-700 dark:text-emerald-300";
    label = "2";
  } else if (score === 1) {
    cls += "text-amber-700 dark:text-amber-300";
    label = "1";
  } else if (score === 0) {
    cls += "text-rose-700 dark:text-rose-300";
    label = "0";
  } else {
    cls += "text-slate-500";
    label = "—";
  }
  return <span className={cls}>{label}</span>;
}

function NotInCoreScorePill() {
  return (
    <span
      className="text-[11px] font-medium text-violet-700 dark:text-violet-300"
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

  let statusCls = "text-[11px] font-medium ";
  if (result.status === "completed") {
    statusCls += "text-emerald-700 dark:text-emerald-300";
  } else if (result.status === "partial") {
    statusCls += "text-amber-700 dark:text-amber-300";
  } else {
    statusCls += "text-rose-700 dark:text-rose-300";
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
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
    <div className="mt-4 bg-rose-50 px-3 py-2 text-sm">
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
    <EvaluationSection
      title="Criteri estesi E1-E5"
      aside={<NotInCoreScorePill />}
    >
      <div className="flex items-start gap-3 bg-slate-50 px-4 py-4">
        <Info
          className="mt-0.5 h-5 w-5 shrink-0 text-slate-500"
          aria-hidden
        />
        <div className="space-y-1.5">
          <p className="text-sm font-medium">
            Risultati estesi non disponibili
          </p>
          <p className="text-xs text-slate-500">
            Questa valutazione è stata eseguita prima dell'introduzione di A5
            (Phase 9.C) e non ha prodotto giudizi sui criteri estesi E1-E5.
            Le run successive popolano questa sezione automaticamente.
          </p>
        </div>
      </div>
    </EvaluationSection>
  );
}

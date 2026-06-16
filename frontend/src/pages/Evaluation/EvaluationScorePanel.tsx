import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { WhyThisResult } from "@/components/WhyThisResult";
import { CORE_CRITERIA } from "@/data/rubric";
import { useTechnicalView } from "@/context/technicalView";
import {
  defaultExpandedCriteria,
  type CriterionExpandInput,
} from "@/lib/verdict";
import {
  CRITERIA_SECTION_ID,
  FOCUS_CRITERIA_EVENT,
  type FocusCriteriaDetail,
} from "@/lib/events";
import type {
  CriterionJudgmentDump,
  EvaluationDetail,
  NACriterionRecord,
} from "@/lib/types";

import { EvaluationSection } from "./EvaluationSection";

interface Props {
  data: EvaluationDetail;
}

/** Display order + readable names/descriptions come from the rubric
 *  (single source of truth, docs/progettazione.md §2.3-2.6). */
const CRITERIA = CORE_CRITERIA.map((c) => ({
  code: c.code,
  name: c.name,
  owner: c.agent,
  description: c.description,
  // deterministic "what adequate looks like" — drives the
  // cosa-correggere/migliorare callout for score 0/1
  improvementTarget:
    c.anchors.find((a) => a.score === 2)?.description ?? null,
}));

/**
 * Phase 10.A R1 — guided/technical score panel.
 *
 * The C1-C9 table is always visible. In guided view it shows
 * code / name / score; technical view adds the owning agent and the
 * confidence. Each expanded row renders the standard `WhyThisResult`
 * composition (Esito → Cosa valuta → Motivazione → Evidenze → Limiti)
 * from already-persisted data — no LLM call.
 *
 * Emphasis: criteria scored 0/1 (and technical NA) are auto-expanded
 * on first load; score 2 stays collapsed and muted. User open/close
 * actions are recorded as per-code overrides that survive refetch.
 */
export function EvaluationScorePanel({ data }: Props) {
  const { technical } = useTechnicalView();
  // Per-code explicit open/close; absence means "follow auto-derived".
  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());

  // Banner chips can ask to expand specific criteria (focus signal).
  useEffect(() => {
    const handler = (e: Event) => {
      const codes =
        (e as CustomEvent<FocusCriteriaDetail>).detail?.codes ?? [];
      if (codes.length === 0) return;
      setOverrides((prev) => {
        const next = new Map(prev);
        for (const code of codes) next.set(code, true);
        return next;
      });
    };
    window.addEventListener(FOCUS_CRITERIA_EVENT, handler);
    return () => window.removeEventListener(FOCUS_CRITERIA_EVENT, handler);
  }, []);

  const scores = data.criterion_scores;

  // Auto-expansion set, recomputed only when the run data changes.
  const autoExpanded = useMemo(
    () => new Set(defaultExpandedCriteria(buildExpandInputs(data))),
    [data],
  );

  const isAggregationReady = scores !== null && scores !== undefined;

  if (!isAggregationReady) {
    return (
      <EvaluationSection
        title="Revisione dei criteri C1-C9"
        aside={
          <span className="text-xs text-muted-foreground">in attesa</span>
        }
      >
        <p className="py-6 text-sm text-muted-foreground">
          I punteggi saranno disponibili al termine della fase di
          aggregazione (evento <code>aggregation_completed</code>).
        </p>
      </EvaluationSection>
    );
  }

  const judgmentByCriterion = buildJudgmentIndex(data);
  const agentErrors = data.agent_errors ?? null;
  const hasAgentErrors =
    agentErrors !== null && Object.keys(agentErrors).length > 0;
  const naCriteria = data.na_criteria ?? [];

  const isExpanded = (code: string) =>
    overrides.has(code) ? overrides.get(code)! : autoExpanded.has(code);

  const toggle = (code: string) =>
    setOverrides((prev) => {
      const next = new Map(prev);
      next.set(code, !isExpanded(code));
      return next;
    });

  const setAll = (value: boolean) =>
    setOverrides(() => new Map(CRITERIA.map((c) => [c.code, value])));

  const anyExpanded = CRITERIA.some((c) => isExpanded(c.code));

  return (
    <div id={CRITERIA_SECTION_ID} className="scroll-mt-24">
      <EvaluationSection
        title="Revisione dei criteri C1-C9"
        aside={
          <button
            type="button"
            onClick={() => setAll(!anyExpanded)}
            className="text-xs font-medium text-slate-600 hover:text-slate-950"
          >
            {anyExpanded ? "Comprimi tutto" : "Espandi tutto"}
          </button>
        }
      >
        {hasAgentErrors ? (
          technical ? (
            <AgentErrorsBanner errors={agentErrors!} />
          ) : (
            <GuidedAgentErrorNotice failed={data.status === "failed"} />
          )
        ) : null}

        <div className="divide-y divide-slate-200/80">
          {CRITERIA.map((c) => {
            const raw = scores[c.code];
            const score: number | null =
              typeof raw === "number" ? raw : null;
            const judgment = judgmentByCriterion.get(c.code) ?? null;
            const agentError = agentErrors?.[c.owner] ?? null;
            return (
              <CriterionRow
                key={c.code}
                code={c.code}
                name={c.name}
                description={c.description}
                improvementTarget={c.improvementTarget}
                owner={c.owner}
                score={score}
                judgment={judgment}
                agentError={agentError}
                expanded={isExpanded(c.code)}
                onToggle={() => toggle(c.code)}
                technical={technical}
              />
            );
          })}
        </div>

        {naCriteria.length > 0 ? (
          technical ? (
            <NaCriteriaList items={naCriteria} />
          ) : (
            <GuidedNaCriteriaNotice items={naCriteria} />
          )
        ) : null}
      </EvaluationSection>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

const ROW_TONE: Record<string, string> = {
  "0": "bg-slate-50/95",
  "1": "bg-slate-50/75",
};

function CriterionRow({
  code,
  name,
  description,
  improvementTarget,
  owner,
  score,
  judgment,
  agentError,
  expanded,
  onToggle,
  technical,
}: {
  code: string;
  name: string;
  description: string;
  improvementTarget: string | null;
  owner: string;
  score: number | null;
  judgment: CriterionJudgmentDump | null;
  agentError: string | null;
  expanded: boolean;
  onToggle: () => void;
  technical: boolean;
}) {
  const isNa = judgment?.is_na ?? score === null;
  const isNaTechnical = Boolean(agentError) && !judgment;
  const tone = score !== null ? ROW_TONE[String(score)] ?? "" : "";
  const muted = score === 2 ? "text-muted-foreground" : "";

  return (
    <article className={tone}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-1 py-3 text-left transition-colors hover:bg-slate-100/60 sm:px-2"
      >
        <span className="text-slate-400">
          {expanded ? (
            <ChevronDown className="h-4 w-4" aria-hidden />
          ) : (
            <ChevronRight className="h-4 w-4" aria-hidden />
          )}
        </span>
        <span className="min-w-0">
          <span className={"flex flex-wrap items-baseline gap-x-2 gap-y-0.5 " + muted}>
            <code className="font-mono text-[11px] font-semibold text-slate-500">
              {code}
            </code>
            <span className="font-medium text-slate-900">{name}</span>
          </span>
          {technical ? (
            <span className="mt-0.5 block text-[11px] text-slate-500">
              Agente {owner} · confidenza {judgment?.confidence ?? "—"}
            </span>
          ) : null}
        </span>
        <ScoreMark score={score} isNa={isNa} />
      </button>
      {expanded ? (
        <div className="px-8 pb-5 pt-1 sm:px-10">
          <WhyThisResult
            score={score}
            isNa={isNa}
            isNaTechnical={isNaTechnical}
            whatItEvaluates={description}
            justification={judgment?.justification ?? null}
            evidences={(judgment?.evidences ?? []).map((e) => ({
              text: e.text,
              sourceField: e.source_field,
            }))}
            improvementTarget={improvementTarget}
            naReason={judgment?.na_reason ?? null}
            confidence={
              (judgment?.confidence as "low" | "medium" | "high" | null) ??
              null
            }
            technical={technical}
          />
        </div>
      ) : null}
    </article>
  );
}

function ScoreMark({ score, isNa }: { score: number | null; isNa: boolean }) {
  if (score === 0) {
    return (
      <span className="text-right">
        <strong className="block text-lg tabular-nums text-rose-700">0</strong>
        <span className="hidden text-[10px] font-medium uppercase text-rose-700 sm:block">
          Criticità
        </span>
      </span>
    );
  }
  if (score === 1) {
    return (
      <span className="text-right">
        <strong className="block text-lg tabular-nums text-amber-700">1</strong>
        <span className="hidden text-[10px] font-medium uppercase text-amber-700 sm:block">
          Da migliorare
        </span>
      </span>
    );
  }
  if (score === 2) {
    return (
      <span className="text-right">
        <strong className="block text-lg font-medium tabular-nums text-slate-500">
          2
        </strong>
        <span className="hidden text-[10px] uppercase text-slate-400 sm:block">
          Adeguato
        </span>
      </span>
    );
  }
  return (
    <span className="text-right text-xs font-medium text-slate-500">
      {isNa ? "NA" : "—"}
    </span>
  );
}

/** Guided-view replacement for the raw AgentErrorsBanner: a plain,
 *  human-readable notice that points to the technical view. Never
 *  exposes stack traces or infrastructure detail. */
function GuidedAgentErrorNotice({ failed }: { failed: boolean }) {
  return (
    <div className="mb-4 bg-slate-100 px-3 py-2.5 text-sm text-slate-600">
      {failed
        ? "La valutazione non è stata completata per un errore tecnico durante l'esecuzione. Passa alla Vista tecnica per vedere i dettagli."
        : "Alcuni controlli non sono stati completati per un errore tecnico; i criteri interessati risultano non valutabili. Passa alla Vista tecnica per i dettagli."}
    </div>
  );
}

function AgentErrorsBanner({ errors }: { errors: Record<string, string> }) {
  return (
    <div className="mb-4 bg-amber-100/60 px-3 py-2 text-sm">
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-300">
        Agenti falliti
      </p>
      <ul className="space-y-0.5 text-xs text-amber-900/90 dark:text-amber-200/90">
        {Object.entries(errors).map(([agent, message]) => (
          <li key={agent}>
            <code className="font-mono">{agent}</code>: {message}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Guided-view summary of NA criteria: lists only the criterion codes
 *  with a plain explanation. Never exposes the raw `source`
 *  (`agent_error`) or `reason` (stack traces / infrastructure). */
function GuidedNaCriteriaNotice({ items }: { items: NACriterionRecord[] }) {
  const codes = Array.from(
    new Set(items.map((i) => i.criterion_code)),
  ).join(", ");
  return (
    <div className="mt-4 bg-slate-100 px-3 py-2.5 text-sm text-slate-600">
      Alcuni criteri non sono stati valutati per un problema tecnico
      {codes ? ` (${codes})` : ""}. Passa alla Vista tecnica per i dettagli.
    </div>
  );
}

function NaCriteriaList({ items }: { items: NACriterionRecord[] }) {
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        Criteri marcati NA
      </h3>
      <ul className="space-y-1 text-sm">
        {items.map((item, i) => (
          <li
            key={`${item.criterion_code}-${i}`}
            className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5"
          >
            <code className="font-mono text-xs">{item.criterion_code}</code>
            <code className="bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
              {item.source}
            </code>
            <span className="text-xs text-slate-500">{item.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function buildJudgmentIndex(
  data: EvaluationDetail,
): Map<string, CriterionJudgmentDump> {
  const out = new Map<string, CriterionJudgmentDump>();
  const outputs = data.agent_outputs ?? null;
  if (!outputs) return out;
  for (const agentOut of Object.values(outputs)) {
    if (!agentOut) continue;
    for (const j of agentOut.judgments) {
      out.set(j.criterion_code, j);
    }
  }
  return out;
}

/** Per-criterion inputs for the auto-expansion rule (R1 §13.7). */
function buildExpandInputs(data: EvaluationDetail): CriterionExpandInput[] {
  const scores = data.criterion_scores ?? {};
  const judgments = buildJudgmentIndex(data);
  const agentErrors = data.agent_errors ?? {};
  const naCriteria = data.na_criteria ?? [];
  return CRITERIA.map((c) => {
    const raw = scores[c.code];
    const score = typeof raw === "number" ? raw : null;
    const judgment = judgments.get(c.code) ?? null;
    const naTechnicalFromList = naCriteria.some(
      (n) => n.criterion_code === c.code && n.source === "agent_error",
    );
    const isNaTechnical =
      score === null &&
      (naTechnicalFromList || (Boolean(agentErrors[c.owner]) && !judgment));
    const hasJustification = Boolean(judgment?.justification?.trim());
    return { code: c.code, score, isNaTechnical, hasJustification };
  });
}

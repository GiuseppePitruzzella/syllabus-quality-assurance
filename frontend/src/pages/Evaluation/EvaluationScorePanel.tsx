import { useEffect, useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";

import { Section } from "@/components/layout/Section";
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
      <Section
        title="Punteggi C1-C9"
        headerAside={
          <span className="text-xs text-muted-foreground">in attesa</span>
        }
        padded={false}
      >
        <p className="px-4 py-6 text-sm text-muted-foreground">
          I punteggi saranno disponibili al termine della fase di
          aggregazione (evento <code>aggregation_completed</code>).
        </p>
      </Section>
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
    <Section
      title="Punteggi C1-C9"
      headerAside={
        <button
          type="button"
          onClick={() => setAll(!anyExpanded)}
          className="text-xs font-medium text-primary hover:underline"
        >
          {anyExpanded ? "Comprimi tutto" : "Espandi tutto"}
        </button>
      }
    >
      {hasAgentErrors ? <AgentErrorsBanner errors={agentErrors!} /> : null}

      <div className="overflow-hidden rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="w-8 px-2 py-2" aria-hidden />
              <th className="w-14 px-3 py-2 text-left font-medium">Crit</th>
              <th className="px-3 py-2 text-left font-medium">Criterio</th>
              {technical ? (
                <th className="w-16 px-3 py-2 text-left font-medium">
                  Agente
                </th>
              ) : null}
              {technical ? (
                <th className="w-24 px-3 py-2 text-left font-medium">
                  Confidenza
                </th>
              ) : null}
              <th className="w-20 px-3 py-2 text-right font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
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
          </tbody>
        </table>
      </div>

      {naCriteria.length > 0 ? <NaCriteriaList items={naCriteria} /> : null}
    </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

const ROW_ACCENT: Record<string, string> = {
  "0": "border-l-2 border-rose-400",
  "1": "border-l-2 border-amber-400",
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
  const accent = score !== null ? ROW_ACCENT[String(score)] ?? "" : "";
  const muted = score === 2 ? "text-muted-foreground" : "";
  const colSpan = technical ? 6 : 4;

  return (
    <>
      <tr
        className={
          "cursor-pointer border-t transition-colors hover:bg-muted/30 " +
          accent
        }
        onClick={onToggle}
      >
        <td className="px-2 py-2 text-muted-foreground">
          <ChevronRight
            className={"h-4 w-4 transition-transform " + (expanded ? "rotate-90" : "")}
            aria-hidden
          />
        </td>
        <td className={"px-3 py-2 font-mono text-xs " + muted}>{code}</td>
        <td className={"px-3 py-2 " + muted}>{name}</td>
        {technical ? (
          <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
            {owner}
          </td>
        ) : null}
        {technical ? (
          <td className="px-3 py-2 text-xs text-muted-foreground">
            {judgment?.confidence ?? "—"}
          </td>
        ) : null}
        <td className="px-3 py-2 text-right">
          <ScoreBadge score={score} isNa={isNa} />
        </td>
      </tr>
      {expanded ? (
        <tr className="border-t bg-muted/20">
          <td colSpan={colSpan} className="px-6 py-3 text-sm">
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
          </td>
        </tr>
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// ScoreBadge / banners
// ---------------------------------------------------------------------------

function ScoreBadge({ score, isNa }: { score: number | null; isNa: boolean }) {
  let cls =
    "inline-flex h-6 w-9 items-center justify-center rounded-md border text-sm font-medium tabular-nums";
  let label: string;

  if (score === 2) {
    // discreet — score 2 carries the least visual weight
    cls += " border-slate-300 bg-slate-100 text-slate-600";
    label = "2";
  } else if (score === 1) {
    cls += " border-amber-400 bg-amber-100 text-amber-900";
    label = "1";
  } else if (score === 0) {
    cls += " border-rose-400 bg-rose-100 text-rose-900";
    label = "0";
  } else {
    cls += " border-border bg-muted text-muted-foreground";
    label = isNa ? "NA" : "—";
  }

  return <span className={cls}>{label}</span>;
}

function AgentErrorsBanner({ errors }: { errors: Record<string, string> }) {
  return (
    <div className="mb-4 rounded-md border border-amber-200 bg-amber-500/10 px-3 py-2 text-sm">
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

function NaCriteriaList({ items }: { items: NACriterionRecord[] }) {
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Criteri marcati NA
      </h3>
      <ul className="space-y-1 text-sm">
        {items.map((item, i) => (
          <li
            key={`${item.criterion_code}-${i}`}
            className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5"
          >
            <code className="font-mono text-xs">{item.criterion_code}</code>
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              {item.source}
            </code>
            <span className="text-xs text-muted-foreground">{item.reason}</span>
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

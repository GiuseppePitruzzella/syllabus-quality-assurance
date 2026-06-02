import { useState } from "react";
import { ChevronRight } from "lucide-react";

import type {
  CriterionJudgmentDump,
  EvaluationDetail,
  NACriterionRecord,
} from "@/lib/types";

interface Props {
  data: EvaluationDetail;
}

/** Display order matches the rubric in docs/progettazione.md (C1..C9). */
const CRITERIA: { code: string; name: string; owner: string }[] = [
  { code: "C1", name: "Completezza strutturale", owner: "A1" },
  { code: "C2", name: "Completezza bilingue", owner: "A1" },
  {
    code: "C3",
    name: "Formulazione dei risultati di apprendimento",
    owner: "A2",
  },
  { code: "C4", name: "Descrittori di Dublino", owner: "A2" },
  { code: "C5", name: "Chiarezza dei prerequisiti", owner: "A1" },
  { code: "C6", name: "Coerenza didattica RA/contenuti", owner: "A3" },
  { code: "C7", name: "Strutturazione contenuti", owner: "A3" },
  { code: "C8", name: "Coerenza didattica RA/verifica", owner: "A3" },
  { code: "C9", name: "Cura editoriale", owner: "A4" },
];

/**
 * Phase 5.9.C — review-mode score panel.
 *
 * Compact table with click-to-expand rows. The collapsed row shows
 * code / name / agent owner / score badge / confidence; the expanded
 * row reveals the agent's justification, the evidence list, the NA
 * reason or the agent-error when applicable. RAG chunks stay in the
 * Agent details tab — this panel is for the docente / presidio, not
 * for pipeline forensics.
 */
export function EvaluationScorePanel({ data }: Props) {
  // Hooks first — rules of hooks: never call after an early return.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const scores = data.criterion_scores;
  const isAggregationReady = scores !== null && scores !== undefined;

  if (!isAggregationReady) {
    return (
      <section className="rounded-lg border bg-card">
        <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
          <h2 className="!m-0 !text-base !font-semibold !tracking-normal">
            Punteggi C1-C9
          </h2>
          <span className="text-xs text-muted-foreground">in attesa</span>
        </div>
        <p className="px-4 py-6 text-sm text-muted-foreground">
          I punteggi saranno disponibili al termine della fase di
          aggregazione (evento <code>aggregation_completed</code>).
        </p>
      </section>
    );
  }

  // Pre-index each criterion's judgment from the owning agent's output.
  const judgmentByCriterion = buildJudgmentIndex(data);
  const agentErrors = data.agent_errors ?? null;
  const hasAgentErrors =
    agentErrors !== null && Object.keys(agentErrors).length > 0;
  const naCriteria = data.na_criteria ?? [];

  const toggle = (code: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  const expandAll = () => setExpanded(new Set(CRITERIA.map((c) => c.code)));
  const collapseAll = () => setExpanded(new Set());
  const anyExpanded = expanded.size > 0;

  return (
    <section className="rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="!m-0 !text-base !font-semibold !tracking-normal">
          Punteggi C1-C9
        </h2>
        <button
          type="button"
          onClick={anyExpanded ? collapseAll : expandAll}
          className="text-xs font-medium text-primary hover:underline"
        >
          {anyExpanded ? "Comprimi tutto" : "Espandi tutto"}
        </button>
      </div>

      <div className="p-4">
        {hasAgentErrors ? (
          <AgentErrorsBanner errors={agentErrors!} />
        ) : null}

        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="w-8 px-2 py-2" aria-hidden />
                <th className="w-14 px-3 py-2 text-left font-medium">Crit</th>
                <th className="px-3 py-2 text-left font-medium">Criterio</th>
                <th className="w-16 px-3 py-2 text-left font-medium">
                  Agente
                </th>
                <th className="w-24 px-3 py-2 text-left font-medium">
                  Confidenza
                </th>
                <th className="w-20 px-3 py-2 text-right font-medium">
                  Score
                </th>
              </tr>
            </thead>
            <tbody>
              {CRITERIA.map((c) => {
                const raw = scores[c.code];
                const score: number | null =
                  typeof raw === "number" ? raw : null;
                const judgment = judgmentByCriterion.get(c.code) ?? null;
                const agentError = agentErrors?.[c.owner] ?? null;
                const isExpanded = expanded.has(c.code);
                return (
                  <CriterionRow
                    key={c.code}
                    code={c.code}
                    name={c.name}
                    owner={c.owner}
                    score={score}
                    judgment={judgment}
                    agentError={agentError}
                    expanded={isExpanded}
                    onToggle={() => toggle(c.code)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>

        {naCriteria.length > 0 ? (
          <NaCriteriaList items={naCriteria} />
        ) : null}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function CriterionRow({
  code,
  name,
  owner,
  score,
  judgment,
  agentError,
  expanded,
  onToggle,
}: {
  code: string;
  name: string;
  owner: string;
  score: number | null;
  judgment: CriterionJudgmentDump | null;
  agentError: string | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="cursor-pointer border-t transition-colors hover:bg-muted/30"
        onClick={onToggle}
      >
        <td className="px-2 py-2 text-muted-foreground">
          <ChevronRight
            className={
              "h-4 w-4 transition-transform " +
              (expanded ? "rotate-90" : "")
            }
            aria-hidden
          />
        </td>
        <td className="px-3 py-2 font-mono text-xs">{code}</td>
        <td className="px-3 py-2">{name}</td>
        <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
          {owner}
        </td>
        <td className="px-3 py-2 text-xs text-muted-foreground">
          {judgment?.confidence ?? "—"}
        </td>
        <td className="px-3 py-2 text-right">
          <ScoreBadge score={score} isNa={judgment?.is_na ?? score === null} />
        </td>
      </tr>
      {expanded ? (
        <tr className="border-t bg-muted/20">
          <td colSpan={6} className="px-6 py-3 text-sm">
            <ExpandedDetails
              judgment={judgment}
              agentError={agentError}
              ownerAgent={owner}
            />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function ExpandedDetails({
  judgment,
  agentError,
  ownerAgent,
}: {
  judgment: CriterionJudgmentDump | null;
  agentError: string | null;
  ownerAgent: string;
}) {
  // Three mutually-exclusive states:
  //   1) the owning agent crashed -> render agent_error, no judgment
  //   2) judgment with is_na=true -> render na_reason as the body
  //   3) regular judgment -> justification + evidences
  if (agentError && !judgment) {
    return (
      <div className="space-y-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-amber-700 dark:text-amber-300">
          Errore agente {ownerAgent}
        </p>
        <p className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-800 dark:text-amber-200">
          {agentError}
        </p>
        <p className="text-xs text-muted-foreground">
          Il criterio è stato marcato NA tecnico dall'aggregatore.
        </p>
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

  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Motivazione
        </p>
        <p className="text-sm leading-relaxed">{judgment.justification}</p>
      </div>

      {judgment.is_na && judgment.na_reason ? (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Motivo NA
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {judgment.na_reason}
          </p>
        </div>
      ) : null}

      {judgment.evidences.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Evidenze testuali
          </p>
          <ul className="space-y-1.5 text-xs">
            {judgment.evidences.map((ev, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <code className="self-start rounded bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  {ev.source_field}
                </code>
                <span className="text-foreground/90">“{ev.text}”</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ScoreBadge / banners
// ---------------------------------------------------------------------------

function ScoreBadge({
  score,
  isNa,
}: {
  score: number | null;
  isNa: boolean;
}) {
  let cls =
    "inline-flex h-6 w-9 items-center justify-center rounded-md border text-sm font-medium tabular-nums";
  let label: string;

  if (score === 2) {
    cls +=
      " border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    label = "2";
  } else if (score === 1) {
    cls +=
      " border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
    label = "1";
  } else if (score === 0) {
    cls +=
      " border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
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

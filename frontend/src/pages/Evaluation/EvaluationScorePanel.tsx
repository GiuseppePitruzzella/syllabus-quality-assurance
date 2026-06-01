import type { EvaluationDetail, NACriterionRecord } from "@/lib/types";

interface Props {
  data: EvaluationDetail;
}

/** Display order matches the rubric in docs/progettazione.md (C1..C9). */
const CRITERIA: { code: string; name: string; owner: string }[] = [
  { code: "C1", name: "Completezza strutturale", owner: "A1" },
  { code: "C2", name: "Completezza bilingue", owner: "A1" },
  { code: "C3", name: "Formulazione dei risultati di apprendimento", owner: "A2" },
  { code: "C4", name: "Descrittori di Dublino", owner: "A2" },
  { code: "C5", name: "Chiarezza dei prerequisiti", owner: "A1" },
  { code: "C6", name: "Coerenza didattica RA/contenuti", owner: "A3" },
  { code: "C7", name: "Strutturazione contenuti", owner: "A3" },
  { code: "C8", name: "Coerenza didattica RA/verifica", owner: "A3" },
  { code: "C9", name: "Cura editoriale", owner: "A4" },
];

/**
 * Phase 5.5.D — score panel for one evaluation.
 *
 * Renders three blocks in order:
 *
 *   1. Aggregate metrics header (CoreScore, coverage, counts)
 *   2. Per-criterion table (one row per C1..C9, score badge + owner)
 *   3. NA criteria + agent_errors detail (only when present)
 *
 * Sober QA palette (no traffic-light shouting): emerald for 2, amber
 * for 1, rose for 0, muted grey for NA.
 */
export function EvaluationScorePanel({ data }: Props) {
  const scores = data.criterion_scores;
  const isAggregationReady = scores !== null && scores !== undefined;

  if (!isAggregationReady) {
    return (
      <section className="rounded-lg border bg-card p-6">
        <header className="mb-2 flex items-baseline justify-between gap-3">
          <h2 className="text-base font-medium">Punteggi C1-C9</h2>
          <span className="text-xs text-muted-foreground">in attesa</span>
        </header>
        <p className="text-sm text-muted-foreground">
          I punteggi saranno disponibili al termine della fase di
          aggregazione (evento <code>aggregation_completed</code>).
        </p>
      </section>
    );
  }

  const evaluatedCount = CRITERIA.filter(
    (c) => typeof scores[c.code] === "number",
  ).length;
  const naCount = CRITERIA.length - evaluatedCount;
  const naCriteria = data.na_criteria ?? [];
  const agentErrors = data.agent_errors ?? null;
  const hasAgentErrors =
    agentErrors !== null && Object.keys(agentErrors).length > 0;

  return (
    <section className="rounded-lg border bg-card p-6">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-base font-medium">Punteggi C1-C9</h2>
      </header>

      <AggregateHeader
        coreScore={data.core_score}
        coverage={data.coverage}
        evaluatedCount={evaluatedCount}
        naCount={naCount}
      />

      {hasAgentErrors ? (
        <AgentErrorsBanner errors={agentErrors!} />
      ) : null}

      <div className="mt-6 overflow-hidden rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Crit</th>
              <th className="px-3 py-2 text-left font-medium">Criterio</th>
              <th className="px-3 py-2 text-left font-medium">Agente</th>
              <th className="px-3 py-2 text-right font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
            {CRITERIA.map((c) => {
              const raw = scores[c.code];
              const score: number | null =
                typeof raw === "number" ? raw : null;
              return (
                <tr key={c.code} className="border-t">
                  <td className="px-3 py-2 font-mono text-xs">{c.code}</td>
                  <td className="px-3 py-2">{c.name}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {c.owner}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <ScoreBadge score={score} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {naCriteria.length > 0 ? (
        <NaCriteriaList items={naCriteria} />
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function AggregateHeader({
  coreScore,
  coverage,
  evaluatedCount,
  naCount,
}: {
  coreScore: number | null;
  coverage: number | null;
  evaluatedCount: number;
  naCount: number;
}) {
  return (
    <dl className="grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-4">
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">
          CoreScore
        </dt>
        <dd className="text-2xl font-semibold tabular-nums">
          {typeof coreScore === "number" ? coreScore.toFixed(2) : "—"}
          <span className="ml-1 text-xs font-normal text-muted-foreground">
            / 2.00
          </span>
        </dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">
          Coverage
        </dt>
        <dd className="text-2xl font-semibold tabular-nums">
          {typeof coverage === "number"
            ? `${Math.round(coverage * 100)}%`
            : "—"}
        </dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">
          Valutati
        </dt>
        <dd className="text-2xl font-semibold tabular-nums">
          {evaluatedCount}
          <span className="ml-1 text-xs font-normal text-muted-foreground">
            / 9
          </span>
        </dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">
          NA
        </dt>
        <dd className="text-2xl font-semibold tabular-nums">{naCount}</dd>
      </div>
    </dl>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  // Sober QA palette: emerald / amber / rose / muted. Border-only
  // background keeps the table readable on dark mode too.
  let cls =
    "inline-flex h-6 w-9 items-center justify-center rounded-md border text-sm font-medium tabular-nums";
  let label: string;

  if (score === 2) {
    cls += " border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    label = "2";
  } else if (score === 1) {
    cls += " border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
    label = "1";
  } else if (score === 0) {
    cls += " border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
    label = "0";
  } else {
    cls += " border-border bg-muted text-muted-foreground";
    label = "NA";
  }

  return <span className={cls}>{label}</span>;
}

function AgentErrorsBanner({ errors }: { errors: Record<string, string> }) {
  return (
    <div className="mt-4 rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm">
      <p className="mb-1 font-medium text-amber-700 dark:text-amber-300">
        Agenti falliti
      </p>
      <ul className="space-y-0.5 text-xs text-amber-700/90 dark:text-amber-300/90">
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
    <div className="mt-6">
      <h3 className="mb-2 text-sm font-medium">Criteri marcati NA</h3>
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

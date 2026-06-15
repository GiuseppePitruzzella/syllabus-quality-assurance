import { Section } from "@/components/layout/Section";
import type {
  AgentOutputDump,
  CriterionJudgmentDump,
  EvaluationDetail,
  RetrievedChunkRef,
} from "@/lib/types";

interface Props {
  data: EvaluationDetail;
}

/**
 * Phase 10.A R1 — technical-only agent inspection.
 *
 * Extracted from the former "Output valutazione" tabs: now a separate
 * section rendered on the EvaluationPage ONLY in Vista tecnica, after
 * the readable report. Holds per-agent judgments, execution metadata,
 * confidence, source fields and the retrieved RAG chunks.
 */
export function AgentDetailsSection({ data }: Props) {
  return (
    <Section title="Dettagli agenti" className="min-w-0">
      <AgentDetailsPanel data={data} />
    </Section>
  );
}

const AGENT_ORDER = ["A1", "A2", "A3", "A4"] as const;

const AGENT_INFO: Record<
  (typeof AGENT_ORDER)[number],
  { label: string; criteria: string[] }
> = {
  A1: { label: "Completezza documentale", criteria: ["C1", "C2", "C5"] },
  A2: { label: "Risultati di apprendimento", criteria: ["C3", "C4"] },
  A3: { label: "Coerenza didattica", criteria: ["C6", "C7", "C8"] },
  A4: { label: "Cura editoriale", criteria: ["C9"] },
};

function AgentDetailsPanel({ data }: { data: EvaluationDetail }) {
  const outputs = data.agent_outputs ?? null;
  const errors = data.agent_errors ?? null;
  if (!outputs && !errors) {
    return (
      <p className="text-sm text-muted-foreground">
        I dettagli per agente saranno disponibili al termine della
        valutazione.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {AGENT_ORDER.map((code) => {
        const out = outputs?.[code] ?? null;
        const err = errors?.[code] ?? null;
        if (!out && !err) return null;
        return <AgentCard key={code} code={code} output={out} error={err} />;
      })}
    </div>
  );
}

function AgentCard({
  code,
  output,
  error,
}: {
  code: string;
  output: AgentOutputDump | null;
  error: string | null;
}) {
  const meta = output?.execution_metadata ?? {};
  const info = (
    AGENT_INFO as Record<string, { label: string; criteria: string[] }>
  )[code];
  return (
    <div className="rounded-md border">
      <header className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 border-b bg-muted/30 px-4 py-3">
        <div className="min-w-0">
          <h3 className="!m-0 flex items-baseline gap-2 text-sm font-semibold">
            <code className="font-mono">{code}</code>
            {info ? (
              <span className="font-normal text-foreground/80">
                · {info.label}
              </span>
            ) : null}
          </h3>
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {info ? (
              <>
                <span>Criteri:</span>
                {info.criteria.map((c) => (
                  <code
                    key={c}
                    className="rounded bg-background px-1.5 py-0.5 font-mono text-[10px]"
                  >
                    {c}
                  </code>
                ))}
              </>
            ) : null}
          </p>
        </div>
        <div className="text-xs text-muted-foreground">
          {meta.prompt_version ? (
            <span>prompt {meta.prompt_version} · </span>
          ) : null}
          {typeof meta.latency_ms === "number"
            ? `${(meta.latency_ms / 1000).toFixed(1)} s · `
            : ""}
          {typeof meta.retry_count === "number"
            ? `retry ${meta.retry_count} · `
            : ""}
          {typeof meta.retrieved_chunks_count === "number"
            ? `${meta.retrieved_chunks_count} chunks`
            : ""}
        </div>
      </header>

      {error ? (
        <div className="border-b px-4 py-2 text-xs text-rose-700 dark:text-rose-300">
          <code className="font-mono">{error}</code>
        </div>
      ) : null}

      {output && output.judgments.length > 0 ? (
        <ul className="divide-y text-sm">
          {output.judgments.map((j) => (
            <JudgmentRow key={j.criterion_code} judgment={j} />
          ))}
        </ul>
      ) : null}

      {output && output.retrieved_chunks.length > 0 ? (
        <RetrievedChunksRow chunks={output.retrieved_chunks} />
      ) : null}
    </div>
  );
}

function JudgmentRow({ judgment }: { judgment: CriterionJudgmentDump }) {
  const score = judgment.score;
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <code className="font-mono text-xs">{judgment.criterion_code}</code>
        <CompactScoreBadge
          score={judgment.is_na ? null : (score as number | null)}
        />
        <span className="text-xs text-muted-foreground">
          confidence: {judgment.confidence}
        </span>
      </div>
      <p className="mt-1 text-sm">{judgment.justification}</p>
      {judgment.evidences.length > 0 ? (
        <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
          {judgment.evidences.map((ev, i) => (
            <li key={i} className="flex gap-1.5">
              <code className="font-mono text-[10px]">{ev.source_field}</code>
              <span>“{ev.text}”</span>
            </li>
          ))}
        </ul>
      ) : null}
      {judgment.is_na && judgment.na_reason ? (
        <p className="mt-1 text-xs text-muted-foreground">
          NA: {judgment.na_reason}
        </p>
      ) : null}
    </li>
  );
}

function RetrievedChunksRow({ chunks }: { chunks: RetrievedChunkRef[] }) {
  return (
    <details className="border-t bg-muted/20">
      <summary className="cursor-pointer list-none px-4 py-2 text-[0.7rem] uppercase tracking-wide text-muted-foreground hover:text-foreground">
        Chunks recuperati (RAG) · {chunks.length}
      </summary>
      <ul className="space-y-0.5 px-4 pb-3 text-xs">
        {chunks.map((c, i) => (
          <li
            key={`${c.chunk_id}-${i}`}
            className="flex flex-wrap items-baseline gap-1.5 font-mono"
          >
            <code className="text-[10px] text-muted-foreground">
              {c.criterion_code}
            </code>
            <code>{c.chunk_id}</code>
            {typeof c.similarity_score === "number" ? (
              <span className="text-muted-foreground">
                ({c.similarity_score.toFixed(2)})
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function CompactScoreBadge({ score }: { score: number | null }) {
  let cls =
    "inline-flex h-5 min-w-[1.75rem] items-center justify-center rounded border px-1 text-xs font-medium tabular-nums";
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
    label = "NA";
  }
  return <span className={cls}>{label}</span>;
}

import type { ReactNode } from "react";

import type { EvaluationDetail, EvaluationProgressEvent } from "@/lib/types";

import { EvaluationSection } from "./EvaluationSection";
import { AgentDetailsSection } from "./AgentDetailsSection";
import { EvaluationProgressTimeline } from "./EvaluationProgressTimeline";

/**
 * Phase 10.A R2 — technical block (full-width, only in Vista tecnica).
 *
 * Execution metadata (moved out of the header), per-agent A1-A4
 * details + RAG chunks, and the terminated-run timeline. The E1-E5
 * RESULTS are NOT here — they are methodological and live in the main
 * column; this block only carries the technical layer.
 */
export function TechnicalBlock({
  data,
  events,
  lastError,
}: {
  data: EvaluationDetail;
  events: EvaluationProgressEvent[];
  lastError: Event | null;
}) {
  return (
    <div className="mt-8 border-t pt-2 divide-y divide-slate-100">
      <EvaluationSection title="Esecuzione">
        <ExecutionMetadata data={data} />
      </EvaluationSection>

      <EvaluationSection title="Dettagli agenti">
        <AgentDetailsSection data={data} />
      </EvaluationSection>

      {events.length > 0 ? (
        <EvaluationSection title="Timeline esecuzione">
          <EvaluationProgressTimeline
            events={events}
            isLive={false}
            isConnected={false}
            lastError={lastError}
            embedded
          />
        </EvaluationSection>
      ) : null}
    </div>
  );
}

function ExecutionMetadata({ data }: { data: EvaluationDetail }) {
  const started = data.started_at ? new Date(data.started_at) : null;
  const finished = data.finished_at ? new Date(data.finished_at) : null;
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3 lg:grid-cols-5">
      <Field label="Avvio">{started ? fmt(started) : "—"}</Field>
      <Field label="Fine">{finished ? fmt(finished) : "—"}</Field>
      <Field label="LLM">{data.llm_model}</Field>
      <Field label="Embedding">
        {data.embedding_model} ({data.embedding_dim}d)
      </Field>
      <Field label="Prompt versions">
        <code className="font-mono">
          {Object.entries(data.prompt_versions)
            .map(([k, v]) => `${k}=${v}`)
            .join(" · ")}
        </code>
      </Field>
      <Field label="RAG">
        top_k {data.rag_top_k} · final_k {data.rag_final_k} · soglia{" "}
        {data.rag_similarity_threshold}
      </Field>
    </dl>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 truncate text-xs text-foreground">{children}</dd>
    </div>
  );
}

function fmt(d: Date): string {
  return d.toLocaleString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

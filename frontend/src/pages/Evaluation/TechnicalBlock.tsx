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
    <section className="mt-12 bg-slate-100/70 px-5 py-2 sm:px-7 lg:px-9">
      <div className="border-b-2 border-slate-300 pb-3 pt-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
          Vista tecnica — dettagli di esecuzione
        </h2>
        <p className="mt-0.5 text-xs text-slate-500">
          Metadati di esecuzione, agenti A1–A4 con frammenti RAG e timeline.
          Non incidono sul giudizio.
        </p>
      </div>
      <div className="divide-y divide-slate-200/80">
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
    </section>
  );
}

function ExecutionMetadata({ data }: { data: EvaluationDetail }) {
  const started = data.started_at ? new Date(data.started_at) : null;
  const finished = data.finished_at ? new Date(data.finished_at) : null;
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-xs sm:grid-cols-3 lg:grid-cols-5">
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

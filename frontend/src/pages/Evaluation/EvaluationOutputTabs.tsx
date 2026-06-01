import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
 * Phase 5.5.E — output tabs (Report / Syllabus / Agent details).
 *
 * The tab strip is rendered even when the report has not been
 * synthesised yet, so the layout stays stable across the lifecycle
 * of one evaluation. Each tab handles its own "in attesa" state.
 *
 * The Syllabus tab is intentionally a light preview (course title +
 * deep link). The full side-by-side split view is scope of phase-5.5.H.
 */
export function EvaluationOutputTabs({ data }: Props) {
  return (
    <section className="rounded-lg border bg-card p-6">
      <Tabs defaultValue="report">
        <TabsList>
          <TabsTrigger value="report">Report</TabsTrigger>
          <TabsTrigger value="syllabus">Syllabus originale</TabsTrigger>
          <TabsTrigger value="agents">Dettagli agenti</TabsTrigger>
        </TabsList>

        <TabsContent value="report" className="mt-4">
          <ReportPanel data={data} />
        </TabsContent>

        <TabsContent value="syllabus" className="mt-4">
          <SyllabusPreview data={data} />
        </TabsContent>

        <TabsContent value="agents" className="mt-4">
          <AgentDetailsPanel data={data} />
        </TabsContent>
      </Tabs>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Report (Markdown)
// ---------------------------------------------------------------------------

function ReportPanel({ data }: { data: EvaluationDetail }) {
  if (!data.final_report) {
    return (
      <p className="text-sm text-muted-foreground">
        Il report sarà disponibile al termine della fase di sintesi
        (evento <code>report_synthesized</code>).
      </p>
    );
  }
  return <ReportMarkdown source={data.final_report} />;
}

/**
 * Sober QA-document styling: small headings, scrollable tables,
 * subtle borders. Nothing screams "blog post"; the goal is a
 * consultable, print-friendly document.
 */
function ReportMarkdown({ source }: { source: string }) {
  return (
    <div className="max-w-none text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => (
            <h1
              className="mt-6 mb-3 text-xl font-semibold tracking-tight first:mt-0"
              {...props}
            />
          ),
          h2: (props) => (
            <h2
              className="mt-6 mb-2 text-base font-semibold tracking-tight first:mt-0"
              {...props}
            />
          ),
          h3: (props) => (
            <h3
              className="mt-4 mb-1.5 text-sm font-semibold tracking-tight first:mt-0"
              {...props}
            />
          ),
          h4: (props) => (
            <h4
              className="mt-3 mb-1 text-sm font-medium first:mt-0"
              {...props}
            />
          ),
          p: (props) => <p className="my-2" {...props} />,
          ul: (props) => (
            <ul className="my-2 list-disc space-y-1 pl-5" {...props} />
          ),
          ol: (props) => (
            <ol className="my-2 list-decimal space-y-1 pl-5" {...props} />
          ),
          li: (props) => <li className="leading-relaxed" {...props} />,
          a: (props) => (
            <a
              className="text-primary underline underline-offset-2 hover:text-primary/80"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),
          blockquote: (props) => (
            <blockquote
              className="my-3 border-l-2 border-muted-foreground/30 pl-3 text-muted-foreground"
              {...props}
            />
          ),
          code: ({ children, className, ...rest }) => {
            const isBlock = /language-/.test(className ?? "");
            return isBlock ? (
              <code
                className="block overflow-x-auto rounded-md bg-muted px-3 py-2 font-mono text-xs"
                {...rest}
              >
                {children}
              </code>
            ) : (
              <code
                className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
                {...rest}
              >
                {children}
              </code>
            );
          },
          pre: (props) => (
            <pre className="my-3 overflow-x-auto" {...props} />
          ),
          table: (props) => (
            <div className="my-3 overflow-x-auto rounded-md border">
              <table className="w-full text-xs" {...props} />
            </div>
          ),
          thead: (props) => (
            <thead
              className="bg-muted/40 text-[0.7rem] uppercase tracking-wide text-muted-foreground"
              {...props}
            />
          ),
          th: (props) => (
            <th
              className="border-b px-2 py-1.5 text-left font-medium"
              {...props}
            />
          ),
          td: (props) => (
            <td className="border-b px-2 py-1.5 align-top" {...props} />
          ),
          hr: () => <hr className="my-4 border-border" />,
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Syllabus (light preview, full split view is phase-5.5.H)
// ---------------------------------------------------------------------------

function SyllabusPreview({ data }: { data: EvaluationDetail }) {
  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        Il syllabus valutato è disponibile nella pagina dedicata. Lo
        split view affiancato report/syllabus arriverà in
        <code className="mx-1">phase-5.5.H</code>.
      </p>
      <div className="rounded-md border p-4">
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
          <Field label="Corso">{data.course_name_snapshot}</Field>
          <Field label="SEUID">
            <code className="font-mono text-xs">
              {data.syllabus_seuid_snapshot}
            </code>
          </Field>
        </dl>
        <div className="mt-4">
          <Link
            to={`/syllabus/${data.syllabus_seuid_snapshot}`}
            className="inline-flex items-center text-sm text-primary underline underline-offset-2 hover:text-primary/80"
          >
            Apri syllabus originale →
          </Link>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agent details (compact: judgments + retrieved chunks per agent)
// ---------------------------------------------------------------------------

const AGENT_ORDER = ["A1", "A2", "A3", "A4"] as const;

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
  return (
    <div className="rounded-md border">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b bg-muted/30 px-4 py-2">
        <h3 className="text-sm font-semibold">
          <code className="font-mono">{code}</code>
          {meta.prompt_version ? (
            <span className="ml-2 text-xs text-muted-foreground">
              prompt: {meta.prompt_version}
            </span>
          ) : null}
        </h3>
        <div className="text-xs text-muted-foreground">
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
    <div className="border-t bg-muted/20 px-4 py-2">
      <p className="mb-1 text-[0.7rem] uppercase tracking-wide text-muted-foreground">
        Chunks recuperati (RAG)
      </p>
      <ul className="space-y-0.5 text-xs">
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
    </div>
  );
}

function CompactScoreBadge({ score }: { score: number | null }) {
  let cls =
    "inline-flex h-5 min-w-[1.75rem] items-center justify-center rounded border px-1 text-xs font-medium tabular-nums";
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

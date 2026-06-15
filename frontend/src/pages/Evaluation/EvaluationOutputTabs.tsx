import { Link } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Section } from "@/components/layout/Section";
import { getSyllabus } from "@/lib/api";
import { useTechnicalView } from "@/context/technicalView";
import type {
  AgentOutputDump,
  CriterionJudgmentDump,
  EvaluationDetail,
  RetrievedChunkRef,
  SyllabusDetail,
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
 * Desktop now offers a side-by-side Report/Syllabus view in the Report
 * tab; mobile and tablet users still use the separate tabs.
 */
export function EvaluationOutputTabs({ data }: Props) {
  const { technical } = useTechnicalView();
  const [tab, setTab] = useState("report");
  const syllabusQuery = useQuery({
    queryKey: ["syllabus", data.syllabus_seuid_snapshot],
    queryFn: () => getSyllabus(data.syllabus_seuid_snapshot),
  });
  const syllabus = syllabusQuery.data ?? null;

  // Derived: if Vista tecnica is off, never resolve to the agents tab.
  const activeTab = !technical && tab === "agents" ? "report" : tab;

  return (
    <Tabs value={activeTab} onValueChange={setTab} className="min-w-0">
      <Section
        className="min-w-0"
        title="Output valutazione"
        headerAside={
          <TabsList className="h-auto max-w-full flex-wrap justify-start overflow-visible">
            <TabsTrigger value="report">Report</TabsTrigger>
            <TabsTrigger value="syllabus">Syllabus originale</TabsTrigger>
            {technical ? (
              <TabsTrigger value="agents">Dettagli agenti</TabsTrigger>
            ) : null}
          </TabsList>
        }
        padded={false}
      >
        <TabsContent value="report" className="mt-0 min-w-0 p-4">
          <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(20rem,0.95fr)]">
            <ReportPanel data={data} />
            <div className="hidden min-w-0 xl:block">
              <SyllabusInlinePanel
                data={data}
                syllabus={syllabus}
                isLoading={syllabusQuery.isLoading}
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="syllabus" className="mt-0 min-w-0 p-4">
          <SyllabusFullPanel
            data={data}
            syllabus={syllabus}
            isLoading={syllabusQuery.isLoading}
          />
        </TabsContent>

        {technical ? (
          <TabsContent value="agents" className="mt-0 min-w-0 p-4">
            <AgentDetailsPanel data={data} />
          </TabsContent>
        ) : null}
      </Section>
    </Tabs>
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
    <div className="max-w-none overflow-visible break-words text-sm leading-relaxed [overflow-wrap:anywhere]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => (
            <h1
              className="!mt-6 !mb-3 !text-[1.25rem] !leading-tight !font-semibold !tracking-normal first:!mt-0"
              {...props}
            />
          ),
          h2: (props) => (
            <h2
              className="!mt-6 !mb-2 !text-[1rem] !leading-snug !font-semibold !tracking-normal first:!mt-0"
              {...props}
            />
          ),
          h3: (props) => (
            <h3
              className="!mt-4 !mb-1.5 !text-sm !font-semibold !tracking-normal first:!mt-0"
              {...props}
            />
          ),
          h4: (props) => (
            <h4
              className="!mt-3 !mb-1 !text-sm !font-medium !tracking-normal first:!mt-0"
              {...props}
            />
          ),
          p: (props) => <p className="my-2 whitespace-normal" {...props} />,
          ul: (props) => (
            <ul className="my-2 list-disc space-y-1 pl-5" {...props} />
          ),
          ol: (props) => (
            <ol className="my-2 list-decimal space-y-1 pl-5" {...props} />
          ),
          li: (props) => (
            <li className="min-w-0 leading-relaxed break-words" {...props} />
          ),
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
                className="block overflow-x-auto whitespace-pre-wrap rounded-md bg-muted px-3 py-2 font-mono text-xs"
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
            <td
              className="border-b px-2 py-1.5 align-top break-words"
              {...props}
            />
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
// Syllabus split/preview
// ---------------------------------------------------------------------------

type SyllabusPanelProps = {
  data: EvaluationDetail;
  syllabus: SyllabusDetail | null;
  isLoading: boolean;
};

function SyllabusInlinePanel({ data, syllabus, isLoading }: SyllabusPanelProps) {
  return (
    <aside className="sticky top-20 max-h-[calc(100vh-6rem)] min-w-0 overflow-y-auto rounded-md border bg-background">
      <SyllabusPanelHeader data={data} compact />
      <div className="p-4">
        <SyllabusBody
          data={data}
          syllabus={syllabus}
          isLoading={isLoading}
          compact
        />
      </div>
    </aside>
  );
}

function SyllabusFullPanel({ data, syllabus, isLoading }: SyllabusPanelProps) {
  return (
    <div className="min-w-0 rounded-md border">
      <SyllabusPanelHeader data={data} />
      <div className="p-4">
        <SyllabusBody
          data={data}
          syllabus={syllabus}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}

function SyllabusPanelHeader({
  data,
  compact = false,
}: {
  data: EvaluationDetail;
  compact?: boolean;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3 border-b bg-muted/20 px-4 py-3">
      <div className="min-w-0">
        <h3 className="text-sm font-semibold">
          {compact ? "Syllabus originale" : "Syllabus valutato"}
        </h3>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {data.course_name_snapshot}
        </p>
      </div>
      <Link
        to={`/syllabus/${data.syllabus_seuid_snapshot}`}
        className="text-xs text-primary underline underline-offset-2 hover:text-primary/80"
      >
        Apri pagina →
      </Link>
    </header>
  );
}

function SyllabusBody({
  data,
  syllabus,
  isLoading,
  compact = false,
}: SyllabusPanelProps & { compact?: boolean }) {
  const [lang, setLang] = useState<"it" | "en">("it");
  const hasEnglish = Boolean(syllabus?.has_english);
  const activeLang = lang === "en" && !hasEnglish ? "it" : lang;

  if (isLoading) {
    return (
      <div className="space-y-3" aria-busy>
        {Array.from({ length: compact ? 4 : 6 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className="h-3 w-24 animate-pulse rounded bg-muted" />
            <div className="h-12 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    );
  }

  if (!syllabus) {
    return (
      <div className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          Non riesco a caricare il contenuto del syllabus in questa vista.
        </p>
        <FallbackSyllabusLink data={data} />
      </div>
    );
  }

  const field = (name: string): string => {
    const key = `${name}_${activeLang}` as keyof SyllabusDetail;
    return String(syllabus[key] ?? "").trim();
  };

  const sections = [
    {
      title: activeLang === "it" ? "Risultati di apprendimento" : "Learning outcomes",
      value: field("learning_outcomes"),
    },
    {
      title: activeLang === "it" ? "Contenuto del corso" : "Course content",
      value: field("course_content"),
    },
    {
      title: activeLang === "it" ? "Prerequisiti" : "Prerequisites",
      value: field("prerequisites"),
    },
    {
      title: activeLang === "it" ? "Metodi di insegnamento" : "Teaching methods",
      value: field("teaching_methods"),
    },
    {
      title:
        activeLang === "it"
          ? "Modalità di verifica"
          : "Assessment methods",
      value: field("assessment_methods"),
    },
    {
      title: activeLang === "it" ? "Riferimenti" : "References",
      value: field("references"),
    },
  ];

  return (
    <div className="min-w-0 space-y-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex rounded-md border bg-muted/30 p-0.5">
          <Button
            size="xs"
            variant={activeLang === "it" ? "secondary" : "ghost"}
            onClick={() => setLang("it")}
          >
            IT
          </Button>
          <Button
            size="xs"
            variant={activeLang === "en" ? "secondary" : "ghost"}
            onClick={() => setLang("en")}
            disabled={!hasEnglish}
          >
            EN
          </Button>
        </div>
        <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.7rem] text-muted-foreground">
          {syllabus.seuid.slice(0, 8)}
        </code>
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-1">
        <Field label="Docente">{syllabus.teacher || "—"}</Field>
        <Field label="Modulo">{syllabus.module || "—"}</Field>
      </dl>

      <div className="space-y-3">
        {sections.map((section) => (
          <SyllabusTextSection
            key={section.title}
            title={section.title}
            value={section.value}
            compact={compact}
          />
        ))}
      </div>
    </div>
  );
}

function SyllabusTextSection({
  title,
  value,
  compact,
}: {
  title: string;
  value: string;
  compact: boolean;
}) {
  return (
    <section className="min-w-0 border-t pt-3 first:border-t-0 first:pt-0">
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      <p
        className={`whitespace-pre-line break-words leading-relaxed text-muted-foreground ${
          compact ? "text-[0.83rem]" : ""
        }`}
      >
        {value || "—"}
      </p>
    </section>
  );
}

function FallbackSyllabusLink({ data }: { data: EvaluationDetail }) {
  return (
    <Link
      to={`/syllabus/${data.syllabus_seuid_snapshot}`}
      className="inline-flex items-center text-sm text-primary underline underline-offset-2 hover:text-primary/80"
    >
      Apri syllabus originale →
    </Link>
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
  const info = (AGENT_INFO as Record<string, { label: string; criteria: string[] }>)[code];
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

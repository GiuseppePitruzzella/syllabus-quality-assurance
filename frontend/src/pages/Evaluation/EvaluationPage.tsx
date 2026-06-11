import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { MetricTile } from "@/components/layout/MetricTile";
import { PageHeader } from "@/components/layout/PageHeader";
import { useEvaluationStream } from "@/hooks/useEvaluationStream";
import { getEvaluation } from "@/lib/api";
import type { EvaluationDetail, EvaluationStatus } from "@/lib/types";

import { EvaluationOutputTabs } from "./EvaluationOutputTabs";
import { EvaluationProgressTimeline } from "./EvaluationProgressTimeline";
import { EvaluationScorePanel } from "./EvaluationScorePanel";
import { ExtendedCriteriaResults } from "./ExtendedCriteriaResults";

const TERMINAL_STATUSES = new Set<EvaluationStatus>([
  "completed",
  "partial",
  "failed",
]);

const POLL_MS = 3000;

/**
 * Phase 5.9.C — review-mode evaluation page.
 *
 * Layout choices reflect the actual use case: a docente / presidio
 * qualità reading a finished evaluation and comparing it against
 * the original syllabus.
 *
 *   - Live run (pending/running): timeline first, then the (empty)
 *     score + output sections that fill in as events arrive.
 *   - Terminated run: header + score + output as primary surfaces;
 *     the SSE timeline drops to a collapsed section at the bottom
 *     when events were accumulated in the current session, and is
 *     hidden entirely on historical runs (no events ever received).
 */
export function EvaluationPage() {
  const { evaluation_uuid } = useParams<{ evaluation_uuid: string }>();

  const { data, isPending, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["evaluation", evaluation_uuid] as const,
    enabled: !!evaluation_uuid,
    queryFn: () => getEvaluation(evaluation_uuid!),
    refetchInterval: (query) => {
      const current = query.state.data;
      if (!current) return POLL_MS;
      return TERMINAL_STATUSES.has(current.status) ? false : POLL_MS;
    },
  });

  // SSE only matters while the run is in flight. Hook called
  // unconditionally; gating happens inside via `enabled`.
  const isLive = data ? !TERMINAL_STATUSES.has(data.status) : false;
  const stream = useEvaluationStream(evaluation_uuid, isLive);

  useEffect(() => {
    if (data?.course_name_snapshot) {
      const prev = document.title;
      document.title = `${data.course_name_snapshot} — valutazione`;
      return () => {
        document.title = prev;
      };
    }
  }, [data?.course_name_snapshot]);

  if (isPending) {
    return <LoadingSkeleton />;
  }
  if (isError) {
    return (
      <ErrorState
        title="Impossibile caricare la valutazione"
        message={error instanceof Error ? error.message : String(error)}
        onRetry={() => refetch()}
      />
    );
  }
  if (!data) {
    return (
      <ErrorState
        title="Valutazione non trovata"
        message={`Nessun record per UUID ${evaluation_uuid ?? "?"}.`}
      />
    );
  }

  const hasStreamEvents = stream.events.length > 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Header data={data} isFetching={isFetching} isLive={isLive} />

      {isLive ? (
        <>
          <EvaluationProgressTimeline
            events={stream.events}
            isLive
            isConnected={stream.isConnected}
            lastError={stream.lastError}
          />
          <EvaluationScorePanel data={data} />
          <ExtendedCriteriaResults data={data} />
          <EvaluationOutputTabs data={data} />
        </>
      ) : (
        <>
          <EvaluationScorePanel data={data} />
          <ExtendedCriteriaResults data={data} />
          <EvaluationOutputTabs data={data} />
          {hasStreamEvents ? (
            <CollapsibleTimeline>
              <EvaluationProgressTimeline
                events={stream.events}
                isLive={false}
                isConnected={false}
                lastError={stream.lastError}
                embedded
              />
            </CollapsibleTimeline>
          ) : null}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function Header({
  data,
  isFetching,
  isLive,
}: {
  data: EvaluationDetail;
  isFetching: boolean;
  isLive: boolean;
}) {
  const startedAt = data.started_at ? new Date(data.started_at) : null;
  const finishedAt = data.finished_at ? new Date(data.finished_at) : null;
  const durationSec =
    typeof data.duration_ms === "number" ? data.duration_ms / 1000 : null;

  const scores = data.criterion_scores;
  const hasScores = scores !== null && scores !== undefined;
  const evaluatedCount = hasScores
    ? Object.values(scores).filter((v) => typeof v === "number").length
    : 0;
  const naCount = hasScores ? 9 - evaluatedCount : 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <Link
          to={`/syllabus/${data.syllabus_seuid_snapshot}`}
          className="text-primary hover:underline"
        >
          ← Torna al syllabus
        </Link>
        <span>·</span>
        <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
          {data.evaluation_uuid.slice(0, 8)}
        </code>
        {isLive && isFetching ? (
          <span className="text-xs text-muted-foreground/80">
            aggiornamento in corso…
          </span>
        ) : null}
      </div>

      <PageHeader
        badge="Valutazione"
        title={data.course_name_snapshot}
        pills={
          <>
            <StatusBadge status={data.status} animate />
            {startedAt ? (
              <span className="text-xs text-muted-foreground">
                avviata il {formatDateTime(startedAt)}
              </span>
            ) : null}
            {durationSec != null ? (
              <span className="text-xs text-muted-foreground">
                · durata {durationSec.toFixed(1)} s
              </span>
            ) : null}
          </>
        }
        actions={
          hasScores ? (
            <ScoreSummary
              coreScore={data.core_score}
              coverage={data.coverage}
              evaluatedCount={evaluatedCount}
              naCount={naCount}
            />
          ) : null
        }
        footer={
          <div className="space-y-3">
            {data.status === "failed" && data.error_message ? (
              <p className="rounded-md border border-rose-200 bg-rose-500/5 px-3 py-2 text-sm text-rose-800">
                {data.error_message}
              </p>
            ) : null}
            <details className="group">
              <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                Dettagli tecnici
              </summary>
              <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3 lg:grid-cols-5">
                <TechField label="Avvio">
                  {startedAt ? formatDateTime(startedAt) : "—"}
                </TechField>
                <TechField label="Fine">
                  {finishedAt ? formatDateTime(finishedAt) : "—"}
                </TechField>
                <TechField label="LLM">{data.llm_model}</TechField>
                <TechField label="Embedding">
                  {data.embedding_model} ({data.embedding_dim}d)
                </TechField>
                <TechField label="Prompt versions">
                  <code className="font-mono">
                    {Object.entries(data.prompt_versions)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(" · ")}
                  </code>
                </TechField>
              </dl>
            </details>
          </div>
        }
      />
    </div>
  );
}

function ScoreSummary({
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
    <>
      <MetricTile
        label="CoreScore"
        value={typeof coreScore === "number" ? coreScore.toFixed(2) : "—"}
        suffix="/ 2.00"
        tone="success"
      />
      <MetricTile
        label="Coverage"
        value={
          typeof coverage === "number"
            ? `${Math.round(coverage * 100)}%`
            : "—"
        }
        tone="muted"
      />
      <MetricTile
        label="Valutati"
        value={String(evaluatedCount)}
        suffix="/ 9"
        tone="muted"
      />
      {naCount > 0 ? (
        <MetricTile label="NA" value={String(naCount)} tone="warning" />
      ) : null}
    </>
  );
}

function TechField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 truncate text-xs text-foreground">{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CollapsibleTimeline — wraps the SSE timeline after the run terminates
// ---------------------------------------------------------------------------

function CollapsibleTimeline({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-lg border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30"
        aria-expanded={open}
      >
        <span className="!text-base !font-semibold !tracking-normal">
          Timeline esecuzione
        </span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          {open ? "nascondi" : "mostra"}
          {open ? (
            <ChevronUp className="h-4 w-4" aria-hidden />
          ) : (
            <ChevronDown className="h-4 w-4" aria-hidden />
          )}
        </span>
      </button>
      {open ? <div className="border-t p-4">{children}</div> : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Loading / error
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="space-y-3 border-b pb-6">
        <div className="h-4 w-40 animate-pulse rounded bg-muted" />
        <div className="h-8 w-2/3 animate-pulse rounded bg-muted" />
      </div>
      {Array.from({ length: 2 }).map((_, i) => (
        <div
          key={i}
          className="h-28 animate-pulse rounded-lg border bg-card"
          aria-hidden
        />
      ))}
    </div>
  );
}

function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="mx-auto max-w-2xl rounded-lg border border-rose-200 bg-rose-500/5 p-6">
      <h2 className="text-lg font-semibold text-rose-800">{title}</h2>
      <p className="mt-2 text-sm text-rose-700">{message}</p>
      {onRetry ? (
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          Riprova
        </Button>
      ) : null}
    </div>
  );
}

function formatDateTime(d: Date): string {
  return d.toLocaleString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { useEvaluationStream } from "@/hooks/useEvaluationStream";
import { getEvaluation } from "@/lib/api";
import type { EvaluationDetail, EvaluationStatus } from "@/lib/types";

import { EvaluationReport } from "./EvaluationReport";
import { EvaluationProgressTimeline } from "./EvaluationProgressTimeline";
import { EvaluationScorePanel } from "./EvaluationScorePanel";
import { ExtendedCriteriaResults } from "./ExtendedCriteriaResults";
import { ExternalDocumentsUsed } from "./ExternalDocumentsUsed";
import { ReviewRail } from "./ReviewRail";
import { TechnicalBlock } from "./TechnicalBlock";
import { SyntheticVerdict } from "@/components/SyntheticVerdict";
import { useTechnicalView } from "@/context/technicalView";

const TERMINAL_STATUSES = new Set<EvaluationStatus>([
  "completed",
  "partial",
  "failed",
]);

const POLL_MS = 3000;

/**
 * Phase 10.A R2 — full-width two-column review layout.
 *
 *   - Live run (pending/running): timeline + progress precede the
 *     review layout in a single column; the full rail appears once
 *     scores are available (terminated).
 *   - Terminated run: header (KPI strip) + two columns — main (C1-C9,
 *     report, extended analysis) and a sticky review rail (verdict,
 *     priorities). Technical surfaces live in a full-width block below,
 *     only in Vista tecnica.
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

  const isLive = data ? !TERMINAL_STATUSES.has(data.status) : false;
  const stream = useEvaluationStream(evaluation_uuid, isLive);
  const { technical } = useTechnicalView();

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

  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-6">
      <Header data={data} isFetching={isFetching} isLive={isLive} />

      {isLive ? (
        <div className="space-y-6">
          <EvaluationProgressTimeline
            events={stream.events}
            isLive
            isConnected={stream.isConnected}
            lastError={stream.lastError}
          />
          <SyntheticVerdict data={data} />
          <EvaluationScorePanel data={data} />
          <ExtendedCriteriaResults data={data} />
          <ExternalDocumentsUsed data={data} />
          <EvaluationReport data={data} />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_22rem]">
            <aside className="xl:col-start-2 xl:row-start-1 xl:sticky xl:top-20 xl:self-start xl:max-h-[calc(100vh-6rem)] xl:overflow-auto">
              <ReviewRail data={data} />
            </aside>
            <div className="min-w-0 space-y-6 xl:col-start-1 xl:row-start-1">
              <EvaluationScorePanel data={data} />
              <EvaluationReport data={data} />
              <ExtendedCriteriaResults data={data} />
              <ExternalDocumentsUsed data={data} />
            </div>
          </div>

          {technical ? (
            <TechnicalBlock
              data={data}
              events={stream.events}
              lastError={stream.lastError}
            />
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
  const durationSec =
    typeof data.duration_ms === "number" ? data.duration_ms / 1000 : null;

  const scores = data.criterion_scores;
  const hasScores = scores !== null && scores !== undefined;
  const evaluatedCount = hasScores
    ? Object.values(scores).filter((v) => typeof v === "number").length
    : 0;

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
        footer={
          <div className="space-y-3">
            {data.status === "failed" && data.error_message ? (
              <p className="rounded-md border border-rose-200 bg-rose-500/5 px-3 py-2 text-sm text-rose-800">
                {data.error_message}
              </p>
            ) : null}
            {hasScores ? (
              <div className="flex flex-wrap items-center gap-x-8 gap-y-1 text-sm">
                <Kpi
                  label="CoreScore"
                  value={
                    typeof data.core_score === "number"
                      ? data.core_score.toFixed(2)
                      : "—"
                  }
                  suffix="/2"
                />
                <Kpi
                  label="Copertura"
                  value={
                    typeof data.coverage === "number"
                      ? `${Math.round(data.coverage * 100)}%`
                      : "—"
                  }
                />
                <Kpi label="Criteri valutati" value={`${evaluatedCount}/9`} />
              </div>
            ) : null}
          </div>
        }
      />
    </div>
  );
}

function Kpi({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <span>
      <span className="text-muted-foreground">{label} </span>
      <span className="font-semibold tabular-nums text-foreground">{value}</span>
      {suffix ? <span className="text-muted-foreground">{suffix}</span> : null}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Loading / error
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-6">
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

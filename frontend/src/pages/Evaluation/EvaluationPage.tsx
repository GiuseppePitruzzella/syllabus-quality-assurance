import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useEvaluationStream } from "@/hooks/useEvaluationStream";
import { getEvaluation } from "@/lib/api";
import type { EvaluationDetail, EvaluationStatus } from "@/lib/types";

import { EvaluationOutputTabs } from "./EvaluationOutputTabs";
import { EvaluationProgressTimeline } from "./EvaluationProgressTimeline";
import { EvaluationScorePanel } from "./EvaluationScorePanel";

const TERMINAL_STATUSES = new Set<EvaluationStatus>([
  "completed",
  "partial",
  "failed",
]);

const POLL_MS = 3000;

/**
 * Phase 5.5.B — single stateful route `/evaluation/:evaluation_uuid`.
 *
 * The page polls `GET /api/evaluations/<uuid>` every 3s while the run
 * is still in flight (`pending` / `running`) and stops once a terminal
 * status arrives (`completed` / `partial` / `failed`). Polling is the
 * fallback when the SSE subscription is not yet wired (5.5.C will
 * layer the realtime stream on top without breaking this page).
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

  // SSE is only meaningful while the run is in flight. Historical
  // (already terminal) records have no active queue on the backend
  // (EvaluationRegistry releases it after the terminal event). The
  // hook must be called unconditionally — gating happens inside via
  // `enabled` so it stays compatible with React's rules of hooks
  // when we render an early loading/error state below.
  const isLive = data ? !TERMINAL_STATUSES.has(data.status) : false;
  const stream = useEvaluationStream(evaluation_uuid, isLive);

  // Update the document title with the course name once we have data.
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
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Header data={data} isFetching={isFetching} isLive={isLive} />

      <EvaluationProgressTimeline
        events={stream.events}
        isLive={isLive}
        isConnected={stream.isConnected}
        lastError={stream.lastError}
        isHistorical={!isLive}
      />

      <EvaluationScorePanel data={data} />

      <EvaluationOutputTabs data={data} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents (kept inline; will be extracted as the page grows)
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

  return (
    <header className="flex flex-col gap-4 border-b pb-6">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <Link
          to={`/syllabus/${data.syllabus_seuid_snapshot}`}
          className="hover:underline"
        >
          ← Torna al syllabus
        </Link>
        <span>·</span>
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
          {data.evaluation_uuid.slice(0, 8)}
        </code>
        {isLive && isFetching ? (
          <span className="text-xs text-muted-foreground/80">
            (aggiornamento in corso…)
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-2xl font-semibold leading-tight">
          {data.course_name_snapshot}
        </h1>
        <StatusPill status={data.status} />
      </div>

      <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Avvio">
          {startedAt ? formatDateTime(startedAt) : "—"}
        </Field>
        <Field label="Fine">
          {finishedAt ? formatDateTime(finishedAt) : "—"}
        </Field>
        <Field label="Durata">
          {durationSec != null ? `${durationSec.toFixed(1)} s` : "—"}
        </Field>
        <Field label="LLM">{data.llm_model}</Field>
        <Field label="Embedding">
          {data.embedding_model} ({data.embedding_dim}d)
        </Field>
        <Field label="Prompt versions">
          <code className="font-mono text-xs">
            {Object.entries(data.prompt_versions)
              .map(([k, v]) => `${k}=${v}`)
              .join(" · ")}
          </code>
        </Field>
      </dl>

      {data.status === "failed" && data.error_message ? (
        <p className="rounded-md border border-destructive/50 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {data.error_message}
        </p>
      ) : null}
    </header>
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
    <div className="flex flex-col">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

function StatusPill({ status }: { status: EvaluationStatus }) {
  // The badge variants don't include success / warning; we layer
  // utility classes on top of the closest base variant.
  const config: Record<
    EvaluationStatus,
    { variant: "default" | "secondary" | "destructive" | "outline"; extra?: string; label: string }
  > = {
    pending: { variant: "secondary", label: "in attesa" },
    running: {
      variant: "default",
      extra: "animate-pulse",
      label: "in esecuzione",
    },
    completed: {
      variant: "outline",
      extra: "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
      label: "completata",
    },
    partial: {
      variant: "outline",
      extra: "border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-300",
      label: "parziale",
    },
    failed: { variant: "destructive", label: "fallita" },
  };
  const c = config[status];
  return (
    <Badge variant={c.variant} className={c.extra}>
      {c.label}
    </Badge>
  );
}

function LoadingSkeleton() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-3 border-b pb-6">
        <div className="h-4 w-40 animate-pulse rounded bg-muted" />
        <div className="h-8 w-2/3 animate-pulse rounded bg-muted" />
        <div className="grid grid-cols-3 gap-x-8 gap-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="flex flex-col gap-1"
              aria-hidden
            >
              <div className="h-3 w-16 animate-pulse rounded bg-muted" />
              <div className="h-4 w-32 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </div>
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="h-28 animate-pulse rounded-lg border border-dashed bg-muted/30"
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
    <div className="mx-auto max-w-2xl rounded-lg border border-destructive/50 bg-destructive/5 p-6">
      <h2 className="text-lg font-semibold text-destructive">{title}</h2>
      <p className="mt-2 text-sm text-destructive/90">{message}</p>
      {onRetry ? (
        <Button
          variant="outline"
          className="mt-4"
          onClick={onRetry}
        >
          Riprova
        </Button>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function formatDateTime(d: Date): string {
  return d.toLocaleString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

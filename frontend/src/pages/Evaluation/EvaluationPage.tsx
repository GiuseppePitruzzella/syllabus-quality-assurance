import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Circle, Download } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useEvaluationStream } from "@/hooks/useEvaluationStream";
import { downloadEvaluationDocx, getEvaluation } from "@/lib/api";
import type { EvaluationDetail, EvaluationStatus } from "@/lib/types";

import { AnnotatedSyllabus } from "./AnnotatedSyllabus";
import { EvaluationProgressTimeline } from "./EvaluationProgressTimeline";
import { EvaluationScorePanel } from "./EvaluationScorePanel";
import { ExtendedCriteriaResults } from "./ExtendedCriteriaResults";
import { ExternalDocumentsUsed } from "./ExternalDocumentsUsed";
import { NormativeCorpusUsed } from "./NormativeCorpusUsed";
import { PriorityStrip } from "./PriorityStrip";
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
 * Phase 10.B/13 — full-width guided review layout.
 *
 *   - Live run (pending/running): timeline + progress precede the guided
 *     reading layout.
 *   - Terminated run: verdict, priorities, annotated syllabus, then C1-C9
 *     review and extended/technical surfaces.
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
    <div className="mx-auto w-full max-w-[1720px] space-y-10">
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
          <AnnotatedSyllabus data={data} />
          <EvaluationScorePanel data={data} />
          <ExtendedCriteriaResults data={data} />
          <NormativeCorpusUsed />
          <ExternalDocumentsUsed data={data} />
        </div>
      ) : (
        <>
          <SyntheticVerdict data={data} />
          {data.status !== "failed" ? <PriorityStrip data={data} /> : null}
          <div className="min-w-0 divide-y divide-slate-200/80">
            <AnnotatedSyllabus data={data} />
            <EvaluationScorePanel data={data} />
            <ExtendedCriteriaResults data={data} />
            <NormativeCorpusUsed />
            <ExternalDocumentsUsed data={data} />
          </div>

          {!technical ? <GuidedTechnicalHint /> : null}

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
  const { technical } = useTechnicalView();
  const [isExporting, setIsExporting] = useState(false);
  const canExport = data.status === "completed" || data.status === "partial";

  async function handleExport() {
    setIsExporting(true);
    try {
      await downloadEvaluationDocx(data.evaluation_uuid);
      toast.success("Documento Word preparato.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Esportazione non riuscita.",
      );
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <header className="space-y-7 pb-2">
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <Link
          to={`/syllabus/${data.syllabus_seuid_snapshot}`}
          className="inline-flex items-center gap-1.5 font-medium text-slate-700 hover:text-slate-950"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Torna al syllabus
        </Link>
        {technical ? (
          <>
            <span aria-hidden>·</span>
            <code className="font-mono text-[11px]">
              run {data.evaluation_uuid.slice(0, 8)}
            </code>
          </>
        ) : null}
        {isLive && isFetching ? (
          <span className="text-xs text-slate-500">
            aggiornamento in corso…
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-5xl">
          <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
            <StatusText status={data.status} isLive={isLive} />
            {startedAt ? <span>Avviata il {formatDateTime(startedAt)}</span> : null}
            {durationSec != null ? <span>{durationSec.toFixed(1)} s</span> : null}
          </div>
          <h1 className="text-3xl font-semibold leading-tight text-slate-950 md:text-5xl">
            {data.course_name_snapshot}
          </h1>
        </div>
        <Button
          variant="outline"
          onClick={handleExport}
          disabled={!canExport || isExporting}
          title={!canExport ? "Disponibile per valutazioni completate o parziali" : undefined}
        >
          <Download className="h-4 w-4" aria-hidden />
          {isExporting ? "Preparazione…" : "Esporta DOCX"}
        </Button>
      </div>

      {data.status === "failed" && data.error_message ? (
        <p className="bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {data.error_message}
        </p>
      ) : null}
    </header>
  );
}

function GuidedTechnicalHint() {
  return (
    <p className="mt-10 border-t border-dashed border-slate-300 pt-4 text-sm text-slate-500">
      I dettagli su agenti, RAG, esecuzione e timeline sono disponibili
      automaticamente per gli account con ruolo tecnico o amministrativo.
    </p>
  );
}

const STATUS_LABEL: Record<EvaluationStatus, string> = {
  pending: "In attesa",
  running: "In esecuzione",
  completed: "Valutazione completata",
  partial: "Valutazione parziale",
  failed: "Valutazione non riuscita",
};

const STATUS_DOT: Record<EvaluationStatus, string> = {
  pending: "fill-slate-400 text-slate-400",
  running: "fill-sky-500 text-sky-500",
  completed: "fill-emerald-500 text-emerald-500",
  partial: "fill-amber-500 text-amber-500",
  failed: "fill-rose-500 text-rose-500",
};

function StatusText({
  status,
  isLive,
}: {
  status: EvaluationStatus;
  isLive: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 font-medium text-slate-700">
      <Circle
        className={
          "h-2.5 w-2.5 " +
          STATUS_DOT[status] +
          (isLive ? " animate-pulse" : "")
        }
        aria-hidden
      />
      {STATUS_LABEL[status]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Loading / error
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[1720px] space-y-6">
      <div className="space-y-3 border-b pb-6">
        <div className="h-4 w-40 animate-pulse rounded bg-muted" />
        <div className="h-8 w-2/3 animate-pulse rounded bg-muted" />
      </div>
      {Array.from({ length: 2 }).map((_, i) => (
        <div
          key={i}
          className="h-28 animate-pulse bg-slate-100"
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

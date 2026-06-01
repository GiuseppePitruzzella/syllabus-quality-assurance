import type { EvaluationProgressEvent } from "@/lib/types";

interface Props {
  events: EvaluationProgressEvent[];
  isLive: boolean;
  isConnected: boolean;
  /** Set when the SSE source dropped before a terminal event arrived. */
  lastError: Event | null;
  /** When true the page shows the placeholder text for historical runs. */
  isHistorical: boolean;
}

/**
 * Phase 5.5.C — vertical timeline of the 8 typed SSE events.
 *
 * The component is purely presentational: it does not own the
 * EventSource, that's `useEvaluationStream`'s job. It renders an
 * append-only list with a marker per event, branching the secondary
 * line on `type` for human-readable details (agent code, latency,
 * core score, etc.).
 */
export function EvaluationProgressTimeline({
  events,
  isLive,
  isConnected,
  lastError,
  isHistorical,
}: Props) {
  if (isHistorical) {
    return (
      <section className="rounded-lg border bg-card p-6">
        <header className="mb-2 flex items-baseline justify-between gap-3">
          <h2 className="text-base font-medium">Progress timeline</h2>
          <span className="text-xs text-muted-foreground">storica</span>
        </header>
        <p className="text-sm text-muted-foreground">
          Questa valutazione è già terminata: lo stream SSE non è più
          disponibile (la coda viene rilasciata dopo la chiusura). Il
          dato finale è leggibile nella sezione report più sotto.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border bg-card p-6">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-base font-medium">Progress timeline</h2>
        <LiveIndicator isLive={isLive} isConnected={isConnected} />
      </header>

      {events.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {isConnected
            ? "In attesa del primo evento dallo stream…"
            : "Nessun evento ricevuto."}
        </p>
      ) : (
        <ol className="relative ml-2 space-y-3 border-l pl-6">
          {events.map((ev, idx) => (
            <TimelineRow key={idx} event={ev} />
          ))}
        </ol>
      )}

      {lastError ? (
        <p className="mt-4 rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          Connessione SSE interrotta prima dell'evento finale. Il
          polling del record proseguirà fino allo stato terminale.
        </p>
      ) : null}
    </section>
  );
}

function LiveIndicator({
  isLive,
  isConnected,
}: {
  isLive: boolean;
  isConnected: boolean;
}) {
  if (!isLive) {
    return (
      <span className="text-xs text-muted-foreground">stream concluso</span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
      aria-live="polite"
    >
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          isConnected
            ? "bg-emerald-500 animate-pulse"
            : "bg-muted-foreground/40"
        }`}
        aria-hidden
      />
      {isConnected ? "live" : "disconnesso"}
    </span>
  );
}

function TimelineRow({ event }: { event: EvaluationProgressEvent }) {
  return (
    <li className="relative">
      <span
        className={`absolute -left-[1.65rem] top-1.5 inline-block h-2.5 w-2.5 rounded-full ring-2 ring-card ${dotColor(event.type)}`}
        aria-hidden
      />
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-sm font-medium">{titleFor(event)}</span>
        {event.agent_code ? (
          <code className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono">
            {event.agent_code}
          </code>
        ) : null}
        <span className="text-xs text-muted-foreground">
          {formatTime(event.timestamp)}
        </span>
      </div>
      {subtitleFor(event) ? (
        <p className="mt-0.5 text-xs text-muted-foreground">
          {subtitleFor(event)}
        </p>
      ) : null}
    </li>
  );
}

// ---------------------------------------------------------------------------
// per-type rendering
// ---------------------------------------------------------------------------

function titleFor(ev: EvaluationProgressEvent): string {
  switch (ev.type) {
    case "evaluation_started":
      return "Valutazione avviata";
    case "agent_started":
      return "Agente avviato";
    case "agent_completed":
      return "Agente completato";
    case "agent_failed":
      return "Agente fallito";
    case "aggregation_completed":
      return "Aggregazione completata";
    case "report_synthesized":
      return "Report sintetizzato";
    case "evaluation_completed":
      return "Valutazione completata";
    case "error":
      return "Errore terminale";
  }
}

function subtitleFor(ev: EvaluationProgressEvent): string | null {
  switch (ev.type) {
    case "evaluation_started":
      return ev.course_name ? `Corso: ${ev.course_name}` : null;
    case "agent_completed": {
      const parts: string[] = [];
      if (typeof ev.latency_ms === "number") {
        parts.push(`${(ev.latency_ms / 1000).toFixed(1)} s`);
      }
      if (typeof ev.n_judgments === "number") {
        parts.push(`${ev.n_judgments} giudizi`);
      }
      return parts.length ? parts.join(" · ") : null;
    }
    case "agent_failed":
      return ev.error_message
        ? `${ev.error_type ?? "error"}: ${ev.error_message}`
        : null;
    case "aggregation_completed": {
      const parts: string[] = [];
      if (ev.status) parts.push(`status: ${ev.status}`);
      if (typeof ev.core_score === "number") {
        parts.push(`CoreScore ${ev.core_score.toFixed(2)}`);
      }
      if (typeof ev.coverage === "number") {
        parts.push(`coverage ${Math.round(ev.coverage * 100)}%`);
      }
      if (typeof ev.n_na === "number" && ev.n_na > 0) {
        parts.push(`${ev.n_na} NA`);
      }
      return parts.length ? parts.join(" · ") : null;
    }
    case "report_synthesized":
      return typeof ev.report_chars === "number"
        ? `${ev.report_chars} caratteri`
        : null;
    case "evaluation_completed": {
      const parts: string[] = [];
      if (ev.status) parts.push(ev.status);
      if (typeof ev.duration_ms === "number") {
        parts.push(`durata ${(ev.duration_ms / 1000).toFixed(1)} s`);
      }
      return parts.length ? parts.join(" · ") : null;
    }
    case "error":
      return ev.error_message
        ? `${ev.error_type ?? "error"}: ${ev.error_message}`
        : null;
    default:
      return null;
  }
}

function dotColor(type: EvaluationProgressEvent["type"]): string {
  switch (type) {
    case "evaluation_started":
      return "bg-blue-500";
    case "agent_started":
      return "bg-blue-400";
    case "agent_completed":
      return "bg-emerald-500";
    case "agent_failed":
      return "bg-amber-500";
    case "aggregation_completed":
      return "bg-violet-500";
    case "report_synthesized":
      return "bg-violet-400";
    case "evaluation_completed":
      return "bg-emerald-600";
    case "error":
      return "bg-destructive";
  }
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

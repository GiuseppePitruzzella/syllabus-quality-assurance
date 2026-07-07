import type {
  EvaluationProgressEvent,
  SseEvent,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
const WITH_CREDENTIALS: EventSourceInit = { withCredentials: true };

export function connectSse(
  jobId: string,
  handlers: {
    onProgress: (event: { current: number; total: number; message: string }) => void;
    onDone: (event: { scraped: number; errors: number }) => void;
    onError: (event: { message: string }) => void;
  }
): () => void {
  const source = new EventSource(
    `${BASE_URL}/scrape/stream/${jobId}`,
    WITH_CREDENTIALS,
  );

  source.onmessage = (e) => {
    const data: SseEvent = JSON.parse(e.data);
    switch (data.type) {
      case "progress":
        handlers.onProgress({
          current: data.current,
          total: data.total,
          message: data.message,
        });
        break;
      case "done":
        handlers.onDone({ scraped: data.scraped, errors: data.errors });
        source.close();
        break;
      case "error":
        handlers.onError({ message: data.message });
        break;
    }
  };

  source.onerror = () => {
    source.close();
  };

  return () => source.close();
}

/**
 * Subscribe to the Server-Sent Events stream of one evaluation
 * (`GET /api/evaluations/{evaluation_uuid}/stream`).
 *
 * The server emits a flat `EvaluationProgressEvent` payload per frame.
 * The 8 typed events are forwarded to a single `onEvent` handler so
 * the caller can branch on `event.type`. Two terminal events close the
 * stream automatically:
 *
 *   - `evaluation_completed` — the run finished successfully
 *   - `error`               — the run failed or timed out
 *
 * On network errors the source is closed but the caller is not
 * notified — pair with React Query's `refetchOnReconnect` or a status
 * GET to reconcile after disconnections.
 *
 * Returns a disposer that closes the EventSource.
 */
export function connectEvaluationSse(
  evaluationUuid: string,
  handlers: {
    onEvent: (event: EvaluationProgressEvent) => void;
    onClose?: () => void;
    onError?: (err: Event) => void;
  },
): () => void {
  const source = new EventSource(
    `${BASE_URL}/evaluations/${evaluationUuid}/stream`,
    WITH_CREDENTIALS,
  );

  source.onmessage = (e) => {
    let event: EvaluationProgressEvent;
    try {
      event = JSON.parse(e.data) as EvaluationProgressEvent;
    } catch {
      return; // ignore malformed frames
    }
    handlers.onEvent(event);
    if (event.type === "evaluation_completed" || event.type === "error") {
      source.close();
      handlers.onClose?.();
    }
  };

  source.onerror = (err) => {
    source.close();
    handlers.onError?.(err);
    handlers.onClose?.();
  };

  return () => source.close();
}

// ---------------------------------------------------------------------------
// Phase 8.D.B — local-document indexing job stream
// ---------------------------------------------------------------------------

/** Stages emitted by the backend's `LocalDocumentIndexingService`. */
export type LocalDocumentProgressStage =
  | "extracting"
  | "chunking"
  | "indexing";

/**
 * Subscribe to `GET /api/local-documents/stream/{job_id}`.
 *
 * The backend emits:
 *   - `progress` events with `message` set to the stage name
 *     (`extracting` -> `chunking` -> `indexing`);
 *   - one terminal `done` (with `scraped` set to chunk count) OR
 *     `error` (with `message` set to the failure reason).
 *
 * Both terminal events automatically close the stream and call
 * `onClose`. Returns a disposer for early cancellation.
 */
export function connectLocalDocumentIndexingStream(
  jobId: string,
  handlers: {
    onProgress: (stage: LocalDocumentProgressStage | string) => void;
    onDone: (event: { chunks_written: number }) => void;
    onError: (event: { message: string }) => void;
    onClose?: () => void;
  },
): () => void {
  const source = new EventSource(
    `${BASE_URL}/local-documents/stream/${jobId}`,
    WITH_CREDENTIALS,
  );

  source.onmessage = (e) => {
    let data: SseEvent;
    try {
      data = JSON.parse(e.data) as SseEvent;
    } catch {
      return;
    }
    switch (data.type) {
      case "progress":
        if (data.message) handlers.onProgress(data.message);
        break;
      case "done":
        handlers.onDone({ chunks_written: data.scraped ?? 0 });
        source.close();
        handlers.onClose?.();
        break;
      case "error":
        handlers.onError({
          message: data.message ?? "Errore sconosciuto",
        });
        source.close();
        handlers.onClose?.();
        break;
    }
  };

  source.onerror = () => {
    source.close();
    handlers.onClose?.();
  };

  return () => source.close();
}

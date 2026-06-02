import type {
  EvaluationProgressEvent,
  SseEvent,
} from "./types";

const BASE_URL = "http://localhost:8000/api";

export function connectSse(
  jobId: string,
  handlers: {
    onProgress: (event: { current: number; total: number; message: string }) => void;
    onDone: (event: { scraped: number; errors: number }) => void;
    onError: (event: { message: string }) => void;
  }
): () => void {
  const source = new EventSource(`${BASE_URL}/scrape/stream/${jobId}`);

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

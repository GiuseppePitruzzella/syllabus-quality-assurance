import { useEffect, useState } from "react";

import {
  connectLocalDocumentIndexingStream,
  type LocalDocumentProgressStage,
} from "@/lib/sse";

export type IndexingProgressState =
  | { kind: "idle" }
  | { kind: "in_progress"; stage: LocalDocumentProgressStage | string }
  | { kind: "done"; chunks_written: number }
  | { kind: "error"; message: string };

interface Options {
  /** Called once when the stream reports `done`. */
  onDone?: (event: { chunks_written: number }) => void;
  /** Called once when the stream reports `error`. */
  onError?: (event: { message: string }) => void;
}

/**
 * Phase 8.D.C — subscribe to a local-document indexing stream.
 *
 * Pass `jobId === null` to skip the subscription (typical for
 * rows that aren't currently being indexed). On unmount the
 * underlying `EventSource` is closed; on a fresh `jobId` the
 * previous stream is disposed first so two callers can't race.
 *
 * The hook returns a state machine the caller renders as a banner
 * / chip. The optional `onDone` and `onError` callbacks let the
 * caller invalidate React Query caches without re-subscribing.
 */
export function useLocalDocumentIndexingProgress(
  jobId: string | null,
  options: Options = {},
): IndexingProgressState {
  const [state, setState] = useState<IndexingProgressState>({ kind: "idle" });

  useEffect(() => {
    if (!jobId) {
      setState({ kind: "idle" });
      return;
    }
    setState({ kind: "in_progress", stage: "extracting" });
    const disconnect = connectLocalDocumentIndexingStream(jobId, {
      onProgress: (stage) => {
        setState({ kind: "in_progress", stage });
      },
      onDone: (e) => {
        setState({ kind: "done", chunks_written: e.chunks_written });
        options.onDone?.(e);
      },
      onError: (e) => {
        setState({ kind: "error", message: e.message });
        options.onError?.(e);
      },
    });
    return disconnect;
    // We intentionally don't depend on `options` — the callbacks
    // are captured at subscription time. Callers that need fresh
    // closures should key on a stable callback or pass jobId=null
    // and re-subscribe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  return state;
}

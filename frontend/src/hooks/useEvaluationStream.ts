import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { connectEvaluationSse } from "@/lib/sse";
import type { EvaluationProgressEvent } from "@/lib/types";

const TERMINAL_TYPES = new Set<EvaluationProgressEvent["type"]>([
  "evaluation_completed",
  "error",
]);

export interface EvaluationStreamState {
  /** Append-only list of events received so far, in arrival order. */
  events: EvaluationProgressEvent[];
  /** The terminal event (``evaluation_completed`` or ``error``) once it arrives. */
  terminalEvent: EvaluationProgressEvent | null;
  /** True while the EventSource is open and accepting frames. */
  isConnected: boolean;
  /** Last EventSource ``error`` event (network drop / 404 / etc.) if any. */
  lastError: Event | null;
}

const INITIAL: EvaluationStreamState = {
  events: [],
  terminalEvent: null,
  isConnected: false,
  lastError: null,
};

/**
 * Subscribe to `/api/evaluations/<uuid>/stream` and accumulate events.
 *
 * When the terminal event arrives (``evaluation_completed`` or ``error``)
 * the source is closed by ``connectEvaluationSse`` and we invalidate
 * the matching React Query cache so any consumer of
 * ``useQuery(["evaluation", uuid])`` will refetch the final row.
 *
 * The hook is a no-op when ``enabled`` is false — used by
 * ``EvaluationPage`` to keep historical (already terminal) runs from
 * opening a doomed source against an expired registry entry.
 */
export function useEvaluationStream(
  evaluationUuid: string | undefined,
  enabled: boolean,
): EvaluationStreamState {
  const [state, setState] = useState<EvaluationStreamState>(INITIAL);
  const queryClient = useQueryClient();
  // Latest stable identity for the queryClient — read inside the SSE
  // callbacks without re-subscribing when the QueryClientProvider
  // re-renders. React 19 forbids ref writes during render, so we keep
  // the ref in sync via a layout-level effect that runs after every
  // commit but doesn't trigger the SSE useEffect.
  const queryClientRef = useRef(queryClient);
  useEffect(() => {
    queryClientRef.current = queryClient;
  });

  useEffect(() => {
    if (!evaluationUuid || !enabled) {
      return;
    }

    // Reset state on each new subscription so a back/forward navigation
    // between two evaluations doesn't mix their timelines. This is the
    // intentional "reset on dep change" pattern: not a cascading render.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset on prop change
    setState({ ...INITIAL, isConnected: true });

    const dispose = connectEvaluationSse(evaluationUuid, {
      onEvent: (event) => {
        setState((prev) => {
          const next: EvaluationStreamState = {
            ...prev,
            events: [...prev.events, event],
          };
          if (TERMINAL_TYPES.has(event.type)) {
            next.terminalEvent = event;
            // Trigger one final GET so the page renders the persisted
            // row exactly as the backend stored it.
            queryClientRef.current.invalidateQueries({
              queryKey: ["evaluation", evaluationUuid],
            });
          }
          return next;
        });
      },
      onError: (err) => {
        setState((prev) => ({ ...prev, lastError: err }));
      },
      onClose: () => {
        setState((prev) => ({ ...prev, isConnected: false }));
      },
    });

    return () => {
      dispose();
    };
  }, [evaluationUuid, enabled]);

  return state;
}

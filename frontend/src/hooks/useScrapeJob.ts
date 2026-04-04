import { useState, useEffect, useCallback, useRef } from "react";
import { connectSse } from "@/lib/sse";

interface ScrapeJobState {
  current: number;
  total: number;
  message: string;
  status: "idle" | "running" | "done" | "error";
  scraped: number;
  errors: number;
}

export function useScrapeJob(onComplete?: () => void) {
  const [state, setState] = useState<ScrapeJobState>({
    current: 0,
    total: 0,
    message: "",
    status: "idle",
    scraped: 0,
    errors: 0,
  });
  const cleanupRef = useRef<(() => void) | null>(null);

  const start = useCallback(
    (jobId: string) => {
      setState((s) => ({ ...s, status: "running", current: 0, total: 0 }));

      const cleanup = connectSse(jobId, {
        onProgress: ({ current, total, message }) => {
          setState((s) => ({ ...s, current, total, message }));
        },
        onDone: ({ scraped, errors }) => {
          setState((s) => ({
            ...s,
            status: "done",
            scraped,
            errors,
          }));
          onComplete?.();
        },
        onError: ({ message }) => {
          setState((s) => ({ ...s, status: "error", message }));
        },
      });

      cleanupRef.current = cleanup;
    },
    [onComplete]
  );

  const reset = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setState({
      current: 0,
      total: 0,
      message: "",
      status: "idle",
      scraped: 0,
      errors: 0,
    });
  }, []);

  useEffect(() => {
    return () => cleanupRef.current?.();
  }, []);

  return { ...state, start, reset };
}

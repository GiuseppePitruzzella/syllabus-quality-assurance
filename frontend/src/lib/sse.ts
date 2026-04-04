import type { SseEvent } from "./types";

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

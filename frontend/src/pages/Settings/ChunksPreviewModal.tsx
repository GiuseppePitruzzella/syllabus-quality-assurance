import { useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { useQuery } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";

import { getLocalDocumentChunks } from "@/lib/api";
import type {
  LocalDocument,
  LocalDocumentChunkPreview,
} from "@/lib/types";

const LIMIT_OPTIONS = [20, 50, 100] as const;

interface Props {
  doc: LocalDocument | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Phase 8.D.D — read-only drill-down on a document's Chroma chunks.
 *
 * Modal opens from the registry row when `status === "indexed"`.
 * Lists chunks for the CURRENT version (older versions stay in
 * Chroma for historical EvaluationResult references but the UI
 * shows what's "live"). Each entry shows id, order, char count,
 * truncated text preview and the boolean `tag_E*` flags as
 * amber chips.
 *
 * Read-only by design: this view is for inspection / debugging,
 * not editing. Re-extraction / re-indexing already lives on
 * the card itself via Modifica + Salva (8.D.C).
 */
export function ChunksPreviewModal({ doc, open, onOpenChange }: Props) {
  const [limit, setLimit] = useState<number>(20);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["local-document-chunks", doc?.id, limit],
    queryFn: () => getLocalDocumentChunks(doc!.id, { limit }),
    enabled: open && doc !== null,
  });

  const chunks: LocalDocumentChunkPreview[] = data ?? [];

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-sm data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[starting-style]:animate-in data-[starting-style]:fade-in-0" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 flex max-h-[min(80vh,720px)] w-[min(760px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border bg-card shadow-lg data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[ending-style]:zoom-out-95 data-[starting-style]:animate-in data-[starting-style]:fade-in-0 data-[starting-style]:zoom-in-95">
          <div className="flex items-start justify-between gap-4 border-b p-5">
            <div className="min-w-0">
              <Dialog.Title className="text-base font-semibold tracking-normal">
                Anteprima chunk
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 truncate text-xs text-muted-foreground">
                {doc ? (
                  <>
                    {doc.title}
                    {" · "}
                    <code className="font-mono">v{doc.version}</code>
                    {" · "}
                    {doc.chunk_count ?? "—"} chunk indicizzati
                  </>
                ) : null}
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Chiudi"
            >
              <X className="h-4 w-4" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="flex items-center justify-between gap-3 border-b px-5 py-2.5">
            <p className="text-[11px] text-muted-foreground">
              Sola lettura · ordinato per <code className="font-mono">chunk_order</code>
            </p>
            <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
              Limite
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="h-7 rounded-md border bg-card px-2 text-xs font-medium hover:border-primary/40 focus-visible:border-primary focus-visible:outline-none"
              >
                {LIMIT_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {isError ? (
              <div className="rounded-md border border-rose-300 bg-rose-500/10 px-3 py-2 text-sm text-rose-900">
                Impossibile caricare i chunk.{" "}
                <span className="text-xs text-rose-800/80">
                  {error instanceof Error ? error.message : String(error)}
                </span>
              </div>
            ) : isLoading ? (
              <LoadingChunks />
            ) : chunks.length === 0 ? (
              <EmptyChunks />
            ) : (
              <ul className="space-y-3">
                {chunks.map((c) => (
                  <ChunkRow key={c.chunk_id} chunk={c} />
                ))}
              </ul>
            )}
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Pieces
// ---------------------------------------------------------------------------

function ChunkRow({ chunk }: { chunk: LocalDocumentChunkPreview }) {
  const tagEntries = Object.entries(chunk.tags ?? {}).sort(([a], [b]) =>
    a.localeCompare(b),
  );
  return (
    <li className="rounded-lg border bg-card px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <span className="inline-flex h-5 w-7 shrink-0 items-center justify-center rounded-md border bg-muted/40 font-mono text-[10px] font-semibold tabular-nums text-muted-foreground">
            {chunk.chunk_order.toString().padStart(2, "0")}
          </span>
          <code className="truncate font-mono text-[11px] text-foreground/80">
            {chunk.chunk_id}
          </code>
        </div>
        <span className="text-[10px] tabular-nums text-muted-foreground">
          {chunk.char_count} char
        </span>
      </div>

      <p className="mt-2 whitespace-pre-wrap rounded-md border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-foreground/90">
        {chunk.text_preview}
      </p>

      {tagEntries.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {tagEntries.map(([key, on]) => {
            const code = key.replace(/^tag_/, "");
            return (
              <code
                key={key}
                className={
                  "rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold transition-colors " +
                  (on
                    ? "bg-amber-500/15 text-amber-900"
                    : "bg-muted/50 text-muted-foreground/70 line-through")
                }
              >
                {code}
              </code>
            );
          })}
        </div>
      ) : null}
    </li>
  );
}

function LoadingChunks() {
  return (
    <ul className="space-y-3" aria-busy>
      {Array.from({ length: 3 }).map((_, i) => (
        <li
          key={i}
          className="h-24 animate-pulse rounded-lg border bg-muted/30"
          aria-hidden
        />
      ))}
    </ul>
  );
}

function EmptyChunks() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 py-10 text-center">
      <Loader2 className="h-5 w-5 text-muted-foreground" aria-hidden />
      <p className="text-sm font-medium text-foreground">
        Nessun chunk per la versione attuale.
      </p>
      <p className="text-xs text-muted-foreground">
        Esegui una reindicizzazione per generarli.
      </p>
    </div>
  );
}

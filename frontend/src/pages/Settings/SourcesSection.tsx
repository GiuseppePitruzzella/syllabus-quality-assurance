import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Eye, FileText, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { CriteriaPicker } from "@/components/CriteriaPicker";
import { Section } from "@/components/layout/Section";
import { Button } from "@/components/ui/button";
import { useLocalDocumentIndexingProgress } from "@/hooks/useLocalDocumentIndexingProgress";
import {
  deleteLocalDocument,
  listLocalDocuments,
  patchLocalDocumentCriteria,
} from "@/lib/api";
import type {
  ExtendedCriterionCode,
  LocalDocument,
  LocalDocumentStatus,
  LocalDocumentType,
} from "@/lib/types";

import {
  DOCUMENT_TYPES,
  STATUS_VISUALS,
  labelForDocumentType,
} from "@/data/sources";
import { ChunksPreviewModal } from "./ChunksPreviewModal";
import { UploadLocalDocumentModal } from "./UploadLocalDocumentModal";

const IN_FLIGHT_STATUSES: LocalDocumentStatus[] = [
  "uploaded",
  "extracting",
  "chunking",
  "indexing",
];

const STATUS_OPTIONS: LocalDocumentStatus[] = [
  "uploaded",
  "extracting",
  "chunking",
  "indexing",
  "indexed",
  "failed",
];

/**
 * Phase 8.D.A — registry surface inside `/settings`.
 *
 * Lists the uploaded external/local documents with a CdL / type /
 * status filter row and a delete affordance per row. The list is
 * intentionally read-only at this step: upload (8.D.B), PATCH
 * enabled_criteria (8.D.C) and chunk preview (8.D.D) follow.
 *
 * Empty state and error state are first-class so a fresh
 * deployment with no documents reads clearly as "the registry is
 * empty, not broken".
 */
export function SourcesSection() {
  const [documentType, setDocumentType] = useState<
    LocalDocumentType | "all"
  >("all");
  const [status, setStatus] = useState<LocalDocumentStatus | "all">("all");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [chunksDoc, setChunksDoc] = useState<LocalDocument | null>(null);

  const queryClient = useQueryClient();

  const filters = {
    document_type: documentType === "all" ? undefined : documentType,
    status: status === "all" ? undefined : status,
  };

  // Refetch every 2s while any document is still on its way to
  // `indexed`. Without it the list shows a stale `extracting` state
  // until the user reloads.
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["local-documents", filters],
    queryFn: () => listLocalDocuments(filters),
    refetchInterval: (query) => {
      const rows = query.state.data ?? [];
      const anyInFlight = rows.some((d) =>
        IN_FLIGHT_STATUSES.includes(d.status),
      );
      return anyInFlight ? 2000 : false;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteLocalDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["local-documents"] });
      toast.success("Documento eliminato");
    },
    onError: (err) => {
      toast.error("Eliminazione fallita", {
        description: err instanceof Error ? err.message : String(err),
      });
    },
  });

  return (
    <Section
      title="Fonti esterne / locali"
      description="Documenti per i criteri estesi E1-E5. Caricamento e indicizzazione automatici."
      headerAside={
        <div className="flex items-center gap-2">
          {data ? (
            <span className="rounded-md border bg-muted/50 px-2 py-0.5 text-[11px] font-medium tabular-nums text-muted-foreground">
              {data.length}
            </span>
          ) : null}
          <Button size="sm" onClick={() => setUploadOpen(true)}>
            <Plus className="h-3.5 w-3.5" aria-hidden />
            Carica documento
          </Button>
        </div>
      }
    >
      <UploadLocalDocumentModal
        open={uploadOpen}
        onOpenChange={setUploadOpen}
      />
      <ChunksPreviewModal
        doc={chunksDoc}
        open={chunksDoc !== null}
        onOpenChange={(open) => {
          if (!open) setChunksDoc(null);
        }}
      />
      <div className="space-y-4">
        <FiltersRow
          documentType={documentType}
          onDocumentTypeChange={setDocumentType}
          status={status}
          onStatusChange={setStatus}
        />

        {isError ? (
          <ErrorBanner error={error} />
        ) : isLoading ? (
          <LoadingRows />
        ) : !data || data.length === 0 ? (
          <EmptyRegistry hasFilters={documentType !== "all" || status !== "all"} />
        ) : (
          <ul className="space-y-2">
            {data.map((doc) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                onDelete={() => deleteMutation.mutate(doc.id)}
                isDeleting={
                  deleteMutation.isPending && deleteMutation.variables === doc.id
                }
                onPreviewChunks={() => setChunksDoc(doc)}
              />
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

function FiltersRow({
  documentType,
  onDocumentTypeChange,
  status,
  onStatusChange,
}: {
  documentType: LocalDocumentType | "all";
  onDocumentTypeChange: (v: LocalDocumentType | "all") => void;
  status: LocalDocumentStatus | "all";
  onStatusChange: (v: LocalDocumentStatus | "all") => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <FilterSelect
        label="Tipo documento"
        value={documentType}
        onChange={(v) => onDocumentTypeChange(v as LocalDocumentType | "all")}
        options={[
          { value: "all", label: "Tutti i tipi" },
          ...DOCUMENT_TYPES.map((t) => ({ value: t.code, label: t.label })),
        ]}
      />
      <FilterSelect
        label="Stato"
        value={status}
        onChange={(v) => onStatusChange(v as LocalDocumentStatus | "all")}
        options={[
          { value: "all", label: "Tutti gli stati" },
          ...STATUS_OPTIONS.map((s) => ({
            value: s,
            label: STATUS_VISUALS[s].label,
          })),
        ]}
      />
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 h-9 w-full rounded-lg border bg-card px-3 text-sm font-medium shadow-xs transition-colors hover:border-primary/40 focus-visible:border-primary focus-visible:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Rows
// ---------------------------------------------------------------------------

function DocumentRow({
  doc,
  onDelete,
  isDeleting,
  onPreviewChunks,
}: {
  doc: LocalDocument;
  onDelete: () => void;
  isDeleting: boolean;
  onPreviewChunks: () => void;
}) {
  const visual = STATUS_VISUALS[doc.status];
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [draftCriteria, setDraftCriteria] = useState<ExtendedCriterionCode[]>(
    doc.enabled_criteria,
  );
  // Active reindex job_id (when the PATCH triggered an async run).
  const [reindexJobId, setReindexJobId] = useState<string | null>(null);

  const reindexState = useLocalDocumentIndexingProgress(reindexJobId, {
    onDone: () => {
      queryClient.invalidateQueries({ queryKey: ["local-documents"] });
      queryClient.invalidateQueries({
        queryKey: ["local-document-chunks", doc.id],
      });
      toast.success("Reindicizzazione completata", {
        description: doc.title,
      });
      setReindexJobId(null);
    },
    onError: (e) => {
      queryClient.invalidateQueries({ queryKey: ["local-documents"] });
      toast.error("Reindicizzazione fallita", { description: e.message });
      setReindexJobId(null);
    },
  });

  const patchMutation = useMutation({
    mutationFn: () => patchLocalDocumentCriteria(doc.id, draftCriteria),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["local-documents"] });
      setEditing(false);
      if (res.job_id) {
        setReindexJobId(res.job_id);
        toast.info("Reindicizzazione avviata", { description: doc.title });
      } else {
        toast.success("Criteri aggiornati", { description: doc.title });
      }
    },
    onError: (err) => {
      toast.error("Aggiornamento criteri fallito", {
        description: err instanceof Error ? err.message : String(err),
      });
    },
  });

  function startEdit() {
    setDraftCriteria(doc.enabled_criteria);
    setEditing(true);
  }
  function cancelEdit() {
    setDraftCriteria(doc.enabled_criteria);
    setEditing(false);
  }
  const hasChanges =
    draftCriteria.length !== doc.enabled_criteria.length ||
    !draftCriteria.every((c) => doc.enabled_criteria.includes(c));

  const isReindexing = reindexState.kind === "in_progress";

  return (
    <li className="rounded-lg border bg-card px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <h3 className="truncate text-sm font-medium text-foreground">
              {doc.title}
            </h3>
            <code className="rounded bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              v{doc.version}
            </code>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {labelForDocumentType(doc.document_type)} · a.a. {doc.academic_year} · CdL #{doc.cdl_id}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={visual.tone} inFlight={visual.in_flight}>
            {visual.label}
          </StatusBadge>
          {!editing && doc.status === "indexed" ? (
            <Button
              variant="outline"
              size="sm"
              onClick={onPreviewChunks}
              disabled={isReindexing || patchMutation.isPending || isDeleting}
              aria-label={`Anteprima chunk di ${doc.title}`}
            >
              <Eye className="h-3.5 w-3.5" aria-hidden />
              Chunk
            </Button>
          ) : null}
          {!editing ? (
            <Button
              variant="outline"
              size="sm"
              onClick={startEdit}
              disabled={isReindexing || patchMutation.isPending || isDeleting}
              aria-label={`Modifica criteri di ${doc.title}`}
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
              Modifica
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={onDelete}
            disabled={isDeleting || isReindexing || patchMutation.isPending}
            aria-busy={isDeleting}
            aria-label={`Elimina ${doc.title}`}
          >
            {isDeleting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="h-3.5 w-3.5" aria-hidden />
            )}
            Elimina
          </Button>
        </div>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-[11px] sm:grid-cols-4">
        <Field label="Chunk">
          <span className="tabular-nums">
            {doc.chunk_count ?? "—"}
          </span>
        </Field>
        <Field label="Criteri">
          {!editing ? (
            doc.enabled_criteria.length > 0 ? (
              <span className="flex flex-wrap gap-1">
                {doc.enabled_criteria.map((c) => (
                  <code
                    key={c}
                    className="rounded bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-amber-900"
                  >
                    {c}
                  </code>
                ))}
              </span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )
          ) : (
            <span className="text-muted-foreground">in modifica</span>
          )}
        </Field>
        <Field label="Hash">
          <code className="font-mono text-[10px] text-muted-foreground">
            {doc.file_hash.slice(0, 12)}
          </code>
        </Field>
        <Field label="Aggiornato">
          <span className="text-muted-foreground">
            {doc.indexed_at
              ? formatDate(doc.indexed_at)
              : doc.status === "failed"
                ? "fallito"
                : "in attesa"}
          </span>
        </Field>
      </dl>

      {editing ? (
        <div className="mt-3 space-y-3 rounded-md border border-amber-200 bg-amber-500/[0.04] p-3">
          <CriteriaPicker
            value={draftCriteria}
            onChange={setDraftCriteria}
            disabled={patchMutation.isPending}
            label="Modifica criteri estesi"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] text-muted-foreground">
              {hasChanges
                ? doc.status === "indexed"
                  ? "Il salvataggio avvia una reindicizzazione automatica."
                  : "Il salvataggio aggiorna i criteri; la reindicizzazione avverrà al prossimo run."
                : "Nessuna modifica."}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={cancelEdit}
                disabled={patchMutation.isPending}
              >
                <X className="h-3.5 w-3.5" aria-hidden />
                Annulla
              </Button>
              <Button
                size="sm"
                onClick={() => patchMutation.mutate()}
                disabled={!hasChanges || patchMutation.isPending}
                aria-busy={patchMutation.isPending}
              >
                {patchMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <Check className="h-3.5 w-3.5" aria-hidden />
                )}
                Salva
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {reindexState.kind === "in_progress" ? (
        <div className="mt-3 flex items-center gap-2 rounded-md border border-cyan-300 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-900">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          Reindicizzazione: {STATUS_VISUALS[reindexState.stage as LocalDocumentStatus]?.label ?? reindexState.stage}
        </div>
      ) : null}

      {!editing && doc.status === "failed" && doc.failure_reason ? (
        <p className="mt-3 rounded-md border border-rose-300 bg-rose-500/10 px-3 py-2 text-xs leading-relaxed text-rose-800">
          {doc.failure_reason}
        </p>
      ) : null}
    </li>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({
  tone,
  inFlight,
  children,
}: {
  tone: "emerald" | "amber" | "rose" | "cyan" | "slate";
  inFlight: boolean;
  children: React.ReactNode;
}) {
  const palette = {
    emerald: "border-emerald-300 bg-emerald-500/10 text-emerald-800",
    amber: "border-amber-300 bg-amber-500/10 text-amber-800",
    rose: "border-rose-300 bg-rose-500/10 text-rose-800",
    cyan: "border-cyan-300 bg-cyan-500/10 text-cyan-800",
    slate: "border-slate-300 bg-slate-500/10 text-slate-700",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${palette[tone]}`}
    >
      {inFlight ? (
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
      ) : (
        <span
          aria-hidden
          className="inline-block h-1.5 w-1.5 rounded-full bg-current opacity-70"
        />
      )}
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function LoadingRows() {
  return (
    <ul className="space-y-2" aria-busy>
      {Array.from({ length: 3 }).map((_, i) => (
        <li
          key={i}
          className="h-20 animate-pulse rounded-lg border bg-muted/30"
          aria-hidden
        />
      ))}
    </ul>
  );
}

function EmptyRegistry({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="rounded-lg border border-dashed bg-muted/30 px-4 py-6 text-center">
      <p className="text-sm font-medium text-foreground">
        {hasFilters
          ? "Nessun documento corrisponde ai filtri selezionati."
          : "Nessun documento caricato per i criteri estesi."}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {hasFilters
          ? "Modifica i filtri o cancellali per vedere tutti i documenti."
          : "Usa «Carica documento» per indicizzare la prima fonte locale o esterna."}
      </p>
    </div>
  );
}

function ErrorBanner({ error }: { error: unknown }) {
  return (
    <div className="rounded-md border border-rose-300 bg-rose-500/10 px-3 py-2 text-sm text-rose-900">
      Impossibile caricare i documenti.{" "}
      <span className="text-xs text-rose-800/80">
        {error instanceof Error ? error.message : String(error)}
      </span>
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

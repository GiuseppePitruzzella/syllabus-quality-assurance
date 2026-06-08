import { useEffect, useMemo, useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";

import { CriteriaPicker } from "@/components/CriteriaPicker";
import { Button } from "@/components/ui/button";
import { DOCUMENT_TYPES, STATUS_VISUALS } from "@/data/sources";
import { getCdl, getDepartments, uploadLocalDocument } from "@/lib/api";
import {
  connectLocalDocumentIndexingStream,
  type LocalDocumentProgressStage,
} from "@/lib/sse";
import type {
  ExtendedCriterionCode,
  LocalDocumentType,
} from "@/lib/types";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".html", ".htm", ".md"];

type Stage =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "indexing"; label: string }
  | { kind: "done" }
  | { kind: "error"; message: string };

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Phase 8.D.B — multipart upload + SSE indexing modal.
 *
 * Form layout is compact (grid-2 on `sm+`), criteria are pre-
 * filled from the document_type's default mapping but stay
 * editable before submit. After submit, the modal stays open
 * and shows the live indexing stage; it auto-closes on `done`,
 * stays open on `error` so the user can see the failure
 * message and retry.
 */
export function UploadLocalDocumentModal({ open, onOpenChange }: Props) {
  const queryClient = useQueryClient();

  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [cdlId, setCdlId] = useState<number | null>(null);
  const [documentType, setDocumentType] =
    useState<LocalDocumentType>("usi_dipartimentali");
  const [academicYear, setAcademicYear] = useState("2025-2026");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<Stage>({ kind: "idle" });

  // Criteria are derived from `documentType` unless the user
  // explicitly overrides them. Tracking the override against its
  // owning type prevents a carry-over of E1 (set while
  // documentType was `sua_cds`) onto a later switch to
  // `usi_dipartimentali` — which would round-trip a 422 from the
  // backend's `ALLOWED_CRITERIA_BY_DOCUMENT_TYPE` guard.
  const [criteriaOverride, setCriteriaOverride] = useState<{
    type: LocalDocumentType;
    value: ExtendedCriterionCode[];
  } | null>(null);
  const defaultsForType = useMemo(
    () =>
      DOCUMENT_TYPES.find((t) => t.code === documentType)?.default_enabled ?? [],
    [documentType],
  );
  const criteria: ExtendedCriterionCode[] =
    criteriaOverride && criteriaOverride.type === documentType
      ? criteriaOverride.value
      : [...defaultsForType];

  // Reset everything when modal closes. Calling setState in an
  // effect is intentional here: the modal is mounted under
  // Dialog.Portal for its whole lifetime, so the standard "remount
  // on key change" trick doesn't apply.
  useEffect(() => {
    if (open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDepartmentId(null);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCdlId(null);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDocumentType("usi_dipartimentali");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAcademicYear("2025-2026");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTitle("");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCriteriaOverride(null);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFile(null);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStage({ kind: "idle" });
  }, [open]);

  const { data: departments = [] } = useQuery({
    queryKey: ["departments"],
    queryFn: getDepartments,
    enabled: open,
  });

  const { data: cdlList = [] } = useQuery({
    queryKey: ["cdl", departmentId],
    queryFn: () => getCdl(departmentId!),
    enabled: open && departmentId !== null,
  });

  // SSE stream lifecycle bound to the indexing job_id.
  const [jobId, setJobId] = useState<string | null>(null);
  useEffect(() => {
    if (!jobId) return;
    const disconnect = connectLocalDocumentIndexingStream(jobId, {
      onProgress: (s: LocalDocumentProgressStage | string) => {
        const visual = STATUS_VISUALS[s as keyof typeof STATUS_VISUALS];
        setStage({
          kind: "indexing",
          label: visual ? visual.label : s,
        });
      },
      onDone: () => {
        setStage({ kind: "done" });
        queryClient.invalidateQueries({ queryKey: ["local-documents"] });
        toast.success("Documento indicizzato");
        setJobId(null);
        // Brief delay so the user sees the green "done" state.
        window.setTimeout(() => onOpenChange(false), 600);
      },
      onError: (e) => {
        setStage({ kind: "error", message: e.message });
        queryClient.invalidateQueries({ queryKey: ["local-documents"] });
        toast.error("Indicizzazione fallita", { description: e.message });
        setJobId(null);
      },
    });
    return disconnect;
  }, [jobId, queryClient, onOpenChange]);

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (cdlId === null) throw new Error("Seleziona un Corso di Laurea");
      if (!file) throw new Error("Seleziona un file");
      if (!title.trim()) throw new Error("Inserisci un titolo");
      if (!academicYear.trim()) throw new Error("Inserisci l'anno accademico");
      return uploadLocalDocument({
        cdl_id: cdlId,
        document_type: documentType,
        academic_year: academicYear.trim(),
        title: title.trim(),
        enabled_criteria: criteria,
        file,
      });
    },
    onSuccess: (data) => {
      // Card appears immediately in the list with status=uploaded.
      queryClient.invalidateQueries({ queryKey: ["local-documents"] });
      if (data.job_id) {
        setJobId(data.job_id);
        setStage({ kind: "indexing", label: "in attesa" });
      } else {
        // Edge case: no job scheduled (shouldn't happen post 8.C).
        setStage({ kind: "done" });
        window.setTimeout(() => onOpenChange(false), 600);
      }
    },
    onError: (err) => {
      setStage({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStage({ kind: "uploading" });
    uploadMutation.mutate();
  }

  const isBusy =
    stage.kind === "uploading" ||
    stage.kind === "indexing" ||
    uploadMutation.isPending;
  const canSubmit =
    cdlId !== null && !!file && title.trim().length > 0 && !isBusy;

  // Departments filter to those that have at least one CdL is too
  // expensive client-side; we just show them all and rely on the
  // dependent select to be empty when needed.
  const departmentOptions = useMemo(
    () => [...departments].sort((a, b) => a.name.localeCompare(b.name)),
    [departments],
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-sm data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[starting-style]:animate-in data-[starting-style]:fade-in-0" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 w-[min(640px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border bg-card p-5 shadow-lg data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[ending-style]:zoom-out-95 data-[starting-style]:animate-in data-[starting-style]:fade-in-0 data-[starting-style]:zoom-in-95">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <Dialog.Title className="text-base font-semibold tracking-normal">
                Carica documento esterno / locale
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-muted-foreground">
                Il documento viene indicizzato automaticamente per i criteri estesi selezionati.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Chiudi"
            >
              <X className="h-4 w-4" aria-hidden />
            </Dialog.Close>
          </div>

          <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FieldSelect
                label="Dipartimento"
                value={departmentId !== null ? String(departmentId) : ""}
                onChange={(v) => {
                  setDepartmentId(v ? Number(v) : null);
                  setCdlId(null);
                }}
                disabled={isBusy}
                options={[
                  { value: "", label: "Seleziona dipartimento" },
                  ...departmentOptions.map((d) => ({
                    value: String(d.id),
                    label: d.name,
                  })),
                ]}
              />
              <FieldSelect
                label="Corso di laurea"
                value={cdlId !== null ? String(cdlId) : ""}
                onChange={(v) => setCdlId(v ? Number(v) : null)}
                disabled={isBusy || departmentId === null}
                options={[
                  {
                    value: "",
                    label:
                      departmentId === null
                        ? "Seleziona prima un dipartimento"
                        : cdlList.length === 0
                          ? "Nessun CdL"
                          : "Seleziona CdL",
                  },
                  ...cdlList.map((c) => ({
                    value: String(c.id),
                    label: `${c.code.toUpperCase()} · ${c.name}`,
                  })),
                ]}
              />
            </div>

            <FieldSelect
              label="Tipo documento"
              value={documentType}
              onChange={(v) => setDocumentType(v as LocalDocumentType)}
              disabled={isBusy}
              options={DOCUMENT_TYPES.map((t) => ({
                value: t.code,
                label: t.label,
              }))}
            />

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[10rem_1fr]">
              <FieldInput
                label="Anno accademico"
                value={academicYear}
                onChange={setAcademicYear}
                placeholder="2025-2026"
                disabled={isBusy}
              />
              <FieldInput
                label="Titolo"
                value={title}
                onChange={setTitle}
                placeholder="Es. Regolamento didattico LM-18"
                disabled={isBusy}
              />
            </div>

            <CriteriaPicker
              value={criteria}
              onChange={(next) =>
                setCriteriaOverride({ type: documentType, value: next })
              }
              defaultsFor={documentType}
              disabled={isBusy}
            />

            <FieldFile
              file={file}
              onFile={setFile}
              disabled={isBusy}
            />

            <StageBanner stage={stage} />

            <div className="flex items-center justify-end gap-2 border-t pt-3">
              <Dialog.Close
                render={
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={stage.kind === "uploading" || stage.kind === "indexing"}
                  />
                }
              >
                Annulla
              </Dialog.Close>
              <Button type="submit" size="sm" disabled={!canSubmit}>
                {stage.kind === "uploading" || stage.kind === "indexing" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <Upload className="h-3.5 w-3.5" aria-hidden />
                )}
                Carica
              </Button>
            </div>
          </form>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Small reusable form pieces
// ---------------------------------------------------------------------------

function FieldSelect({
  label,
  value,
  onChange,
  options,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="mt-1 h-9 w-full rounded-lg border bg-card px-3 text-sm font-medium shadow-xs transition-colors hover:border-primary/40 focus-visible:border-primary focus-visible:outline-none disabled:opacity-50"
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

function FieldInput({
  label,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="mt-1 h-9 w-full rounded-lg border bg-card px-3 text-sm shadow-xs transition-colors hover:border-primary/40 focus-visible:border-primary focus-visible:outline-none disabled:opacity-50"
      />
    </label>
  );
}

function FieldFile({
  file,
  onFile,
  disabled,
}: {
  file: File | null;
  onFile: (f: File | null) => void;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        File
      </span>
      <input
        type="file"
        accept={ALLOWED_EXTENSIONS.join(",")}
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        disabled={disabled}
        className="mt-1 block w-full text-xs file:mr-3 file:rounded-md file:border file:border-input file:bg-card file:px-3 file:py-1.5 file:text-xs file:font-medium hover:file:border-primary/40 hover:file:bg-primary/5 disabled:opacity-50"
      />
      <p className="mt-1 text-[10px] text-muted-foreground">
        Estensioni accettate: {ALLOWED_EXTENSIONS.join(", ")}
        {file ? ` · ${(file.size / 1024).toFixed(1)} kB` : ""}
      </p>
    </label>
  );
}

function StageBanner({ stage }: { stage: Stage }) {
  if (stage.kind === "idle") return null;
  if (stage.kind === "uploading") {
    return (
      <Banner tone="cyan">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Caricamento del file in corso...
      </Banner>
    );
  }
  if (stage.kind === "indexing") {
    return (
      <Banner tone="cyan">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Indicizzazione: {stage.label}
      </Banner>
    );
  }
  if (stage.kind === "done") {
    return <Banner tone="emerald">Documento indicizzato.</Banner>;
  }
  return (
    <Banner tone="rose">
      <span className="font-medium">Errore:</span>
      <span className="text-rose-900/90"> {stage.message}</span>
    </Banner>
  );
}

function Banner({
  tone,
  children,
}: {
  tone: "cyan" | "emerald" | "rose";
  children: React.ReactNode;
}) {
  const palette = {
    cyan: "border-cyan-300 bg-cyan-500/10 text-cyan-900",
    emerald: "border-emerald-300 bg-emerald-500/10 text-emerald-900",
    rose: "border-rose-300 bg-rose-500/10 text-rose-900",
  };
  return (
    <div
      className={`flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-xs ${palette[tone]}`}
    >
      {children}
    </div>
  );
}

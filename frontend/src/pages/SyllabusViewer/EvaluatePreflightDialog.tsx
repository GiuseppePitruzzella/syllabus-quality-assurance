import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Dialog } from "@base-ui/react/dialog";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleMinus,
  FileText,
  Info,
  Loader2,
  Settings2,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ResolutionReasonPill } from "@/components/ResolutionReasonPill";
import { labelForDocumentType } from "@/data/sources";
import {
  ApiError,
  getResolutionPreview,
  startEvaluation,
} from "@/lib/api";
import type {
  ExtendedCriterionCode,
  ResolutionPreview,
  ResolutionPreviewCandidate,
  ResolutionPreviewCriterion,
  SelectedDocumentValidationCode,
} from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  seuid: string;
  courseName: string;
}

/** Display order matches rubric.ts / EXTENDED_CRITERIA_ORDER. */
const EXTENDED_ORDER: readonly ExtendedCriterionCode[] = [
  "E1",
  "E2",
  "E3",
  "E4",
  "E5",
];

const CRITERION_LABELS: Record<ExtendedCriterionCode, string> = {
  E1: "Allineamento con SUA-CdS",
  E2: "Allineamento con Matrice di Tuning",
  E3: "Coerenza con Regolamento didattico",
  E4: "Coerenza cross-lingua",
  E5: "Aderenza agli usi dipartimentali / di CdL",
};

/**
 * Phase 9.E.2 — pre-run preflight dialog.
 *
 * Triggered by the ``Valuta`` button on the SyllabusViewer. The
 * dialog **always** opens before a run starts: showing the user
 * which documents will feed each E1-E5 criterion is the
 * methodological invariant of Phase 9.E (the "informational
 * perimeter" of the evaluation is never implicit).
 *
 * Layout
 *   - Header: course name + protocol intro
 *   - Per-criterion block: served_by + auto resolution + NA reason
 *   - Footer:
 *       * primary: "Avvia valutazione" → POST /api/evaluate
 *       * secondary: "Personalizza documenti" → expand to show
 *         alternative versions per criterion (radio per chain)
 *   - On submit:
 *       * if no override was selected, sends a body-less POST
 *         (resolver's standard ladder applies);
 *       * otherwise sends ``{selected_document_ids: [...]}``.
 *         Server-side 422 with a structured ``code`` is surfaced
 *         as an actionable error banner.
 *
 * State is reset every time the dialog opens so consecutive runs
 * never inherit a stale selection.
 */
export function EvaluatePreflightDialog({
  open,
  onOpenChange,
  seuid,
  courseName,
}: Props) {
  const navigate = useNavigate();
  const [customize, setCustomize] = useState(false);
  // Map: chain_key → local_document_id selected by the user.
  // Phase 9.E.2.fix: keyed by *chain* (not criterion) so an
  // override on one chain doesn't blank out the auto pick on
  // sibling chains. The multi-chain E5 case (e.g.
  // ``usi_dipartimentali`` + ``linee_guida_cdl``) needs this:
  // the resolver picks one document per chain and the dialog
  // must allow per-chain overrides while keeping the others on
  // their auto picks.
  const [selection, setSelection] = useState<Record<string, number>>({});
  const [errorBanner, setErrorBanner] = useState<{
    message: string;
    code?: SelectedDocumentValidationCode;
  } | null>(null);

  // Reset every time the dialog opens so the next run starts from
  // the resolver's defaults rather than from a leftover selection.
  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset on open
    setCustomize(false);
    setSelection({});
    setErrorBanner(null);
  }, [open]);

  const previewQuery = useQuery({
    enabled: open,
    queryKey: ["resolutionPreview", seuid] as const,
    queryFn: () => getResolutionPreview(seuid),
  });

  const selectedIds = useMemo(() => {
    const ids = Object.values(selection).filter(
      (v): v is number => typeof v === "number",
    );
    // De-duplicate defensively even though the UI guarantees
    // uniqueness per criterion.
    return Array.from(new Set(ids));
  }, [selection]);

  const startMutation = useMutation({
    mutationFn: () =>
      // selectedIds is the union of every per-chain override.
      // Chains not in ``selection`` continue with the resolver's
      // automatic pick — exactly the additive semantics 9.E.1
      // documents for ``selected_document_ids``.
      startEvaluation(seuid, { selectedDocumentIds: selectedIds }),
    onSuccess: (data) => {
      onOpenChange(false);
      navigate(`/evaluation/${data.evaluation_uuid}`);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setErrorBanner({
          message: explainValidationCode(err.code as
            | SelectedDocumentValidationCode
            | undefined, err.message),
          code: err.code as SelectedDocumentValidationCode | undefined,
        });
      } else {
        const fallback = err instanceof Error ? err.message : String(err);
        setErrorBanner({ message: fallback });
        toast.error("Avvio valutazione fallito", {
          description: fallback,
        });
      }
    },
  });

  const isBusy = startMutation.isPending;
  const preview = previewQuery.data;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-sm data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[starting-style]:animate-in data-[starting-style]:fade-in-0" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100vh-2rem)] w-[min(880px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-lg border bg-card shadow-lg data-[ending-style]:animate-out data-[ending-style]:fade-out-0 data-[ending-style]:zoom-out-95 data-[starting-style]:animate-in data-[starting-style]:fade-in-0 data-[starting-style]:zoom-in-95">
          <div className="flex items-start justify-between gap-4 border-b p-5">
            <div className="min-w-0 space-y-0.5">
              <Dialog.Title className="text-base font-semibold tracking-normal">
                Configura la valutazione
              </Dialog.Title>
              <Dialog.Description className="text-xs text-muted-foreground">
                {courseName} — controlla quali criteri estesi sono disponibili
                e quali fonti verranno utilizzate.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Chiudi"
            >
              <X className="h-4 w-4" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4">
            {previewQuery.isPending ? (
              <PreviewSkeleton />
            ) : previewQuery.isError || !preview ? (
              <PreviewError
                message={
                  previewQuery.error instanceof Error
                    ? previewQuery.error.message
                    : "Impossibile caricare la preview di risoluzione."
                }
                onRetry={() => previewQuery.refetch()}
              />
            ) : (
              <PreviewBody
                preview={preview}
                customize={customize}
                onToggleCustomize={() => setCustomize((v) => !v)}
                selection={selection}
                onSelectChain={(chainKey, docId) =>
                  setSelection((prev) => ({ ...prev, [chainKey]: docId }))
                }
                onResetChain={(chainKey) =>
                  setSelection((prev) => {
                    const next = { ...prev };
                    delete next[chainKey];
                    return next;
                  })
                }
              />
            )}

            {errorBanner ? (
              <div className="mt-4 flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-xs text-rose-800 dark:text-rose-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                <div className="space-y-1">
                  <p className="font-medium uppercase tracking-wide">
                    Selezione non valida
                  </p>
                  <p>{errorBanner.message}</p>
                  {errorBanner.code ? (
                    <p className="text-[10px] text-rose-700/80">
                      <code className="font-mono">code:{errorBanner.code}</code>
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          <div className="flex items-center justify-between gap-2 border-t bg-muted/30 px-5 py-3">
            <p className="text-[11px] text-muted-foreground">
              {selectedIds.length === 0
                ? "Scelta automatica delle fonti attiva."
                : `${selectedIds.length} ${
                    selectedIds.length === 1
                      ? "fonte personalizzata"
                      : "fonti personalizzate"
                  }; le altre restano automatiche.`}
            </p>
            <div className="flex items-center gap-2">
              <Dialog.Close
                render={
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isBusy}
                  />
                }
              >
                Annulla
              </Dialog.Close>
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  setErrorBanner(null);
                  startMutation.mutate();
                }}
                disabled={isBusy || previewQuery.isPending || !preview}
              >
                {isBusy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" aria-hidden />
                )}
                {isBusy ? "Avvio…" : "Avvia valutazione"}
              </Button>
            </div>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Preview body
// ---------------------------------------------------------------------------

function PreviewBody({
  preview,
  customize,
  onToggleCustomize,
  selection,
  onSelectChain,
  onResetChain,
}: {
  preview: ResolutionPreview;
  customize: boolean;
  onToggleCustomize: () => void;
  selection: Record<string, number>;
  onSelectChain: (chainKey: string, docId: number) => void;
  onResetChain: (chainKey: string) => void;
}) {
  const criteria = EXTENDED_ORDER
    .map((code) => preview.by_criterion[code])
    .filter((criterion): criterion is ResolutionPreviewCriterion =>
      criterion !== undefined,
    );
  const applicable = criteria.filter((criterion) => criterion.applicable);
  const registryCriteria = criteria.filter(
    (criterion) =>
      criterion.served_by === "registry" && criterion.applicable,
  );
  const e4Available = preview.by_criterion.E4?.applicable ?? false;
  const canCustomizeSources = registryCriteria.some((criterion) =>
    groupByChain(criterion.candidates).some(
      (group) => group.candidates.filter((candidate) => candidate.selectable).length > 1,
    ),
  );

  return (
    <div className="space-y-5">
      <EvaluationScopeSummary
        applicableCount={applicable.length}
        totalCount={criteria.length}
      />

      <section aria-labelledby="extended-criteria-heading">
        <div className="mb-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">
            Passaggio 1
          </p>
          <h3
            id="extended-criteria-heading"
            className="mt-0.5 text-sm font-semibold"
          >
            Criteri estesi disponibili
          </h3>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-muted-foreground">
            Non devi attivarli manualmente: ogni criterio viene valutato quando
            la fonte necessaria è disponibile. Gli altri saranno indicati come
            non valutabili (NA).
          </p>
        </div>
        <div className="grid border-t sm:grid-cols-2">
          {criteria.map((criterion, index) => (
            <div
              key={criterion.criterion_code}
              className={
                "border-b px-3 " + (index % 2 === 0 ? "sm:border-r" : "")
              }
            >
              <CriterionScopeRow criterion={criterion} />
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="document-sources-heading">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">
              Passaggio 2
            </p>
            <h3
              id="document-sources-heading"
              className="mt-0.5 text-sm font-semibold"
            >
              Fonti della valutazione estesa
            </h3>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-muted-foreground">
              {canCustomizeSources
                ? "Il sistema ha già scelto la versione più adatta di ogni documento. Personalizza soltanto se vuoi usare una versione diversa."
                : "Il sistema ha già scelto la versione più adatta di ogni documento. Non sono disponibili versioni alternative."}
            </p>
          </div>
          {canCustomizeSources ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onToggleCustomize}
              aria-expanded={customize}
            >
              <Settings2 className="h-3.5 w-3.5" aria-hidden />
              {customize ? "Chiudi selezione" : "Modifica fonti"}
              {customize ? (
                <ChevronUp className="h-3.5 w-3.5" aria-hidden />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" aria-hidden />
              )}
            </Button>
          ) : null}
        </div>

        <div className="space-y-2">
          {registryCriteria.map((criterion) => (
            <CriterionCard
              key={criterion.criterion_code}
              criterion={criterion}
              customize={customize}
              selection={selection}
              onSelectChain={onSelectChain}
              onResetChain={onResetChain}
            />
          ))}

          {e4Available ? (
            <div className="flex items-start gap-3 border-y px-1 py-3 text-xs">
              <CheckCircle2
                className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600"
                aria-hidden
              />
              <div>
                <p className="font-medium">E4 usa il syllabus stesso</p>
                <p className="mt-0.5 leading-5 text-muted-foreground">
                  La coerenza cross-lingua confronta direttamente le sezioni
                  italiane e inglesi. Non richiede documenti dal registry.
                </p>
              </div>
            </div>
          ) : null}

          {registryCriteria.length === 0 && !e4Available ? (
            <div className="flex items-start gap-2 border-y px-1 py-3 text-xs text-muted-foreground">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <p>
                Nessuna fonte estesa è disponibile. La valutazione C1-C9 può
                comunque essere avviata normalmente.
              </p>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function EvaluationScopeSummary({
  applicableCount,
  totalCount,
}: {
  applicableCount: number;
  totalCount: number;
}) {
  return (
    <div className="grid gap-3 border-y bg-muted/20 px-1 py-3 sm:grid-cols-2">
      <div className="flex items-start gap-3">
        <CheckCircle2
          className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600"
          aria-hidden
        />
        <div>
          <p className="text-xs font-semibold">CoreScore</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            I criteri C1-C9 sono sempre inclusi.
          </p>
        </div>
      </div>
      <div className="flex items-start gap-3 sm:border-l sm:pl-4">
        <Info
          className="mt-0.5 h-4 w-4 shrink-0 text-primary"
          aria-hidden
        />
        <div>
          <p className="text-xs font-semibold">Analisi estesa</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {applicableCount} di {totalCount} criteri E1-E5 disponibili. Non
            modificano il CoreScore.
          </p>
        </div>
      </div>
    </div>
  );
}

function CriterionScopeRow({
  criterion,
}: {
  criterion: ResolutionPreviewCriterion;
}) {
  const available = criterion.applicable;
  return (
    <div className="py-2.5">
      <div className="flex min-w-0 items-start gap-3">
        {available ? (
          <CheckCircle2
            className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600"
            aria-hidden
          />
        ) : (
          <CircleMinus
            className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
            aria-hidden
          />
        )}
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <code className="font-mono text-[11px] font-semibold text-primary">
              {criterion.criterion_code}
            </code>
            <span className="text-xs font-medium">
              {CRITERION_LABELS[criterion.criterion_code]}
            </span>
          </div>
          <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[11px] leading-4">
            <span className="text-muted-foreground">
              {criterionSourceDescription(criterion)}
            </span>
            <span
              className={
                "font-medium " +
                (available ? "text-emerald-700" : "text-muted-foreground")
              }
            >
              {available ? "Sarà valutato" : "Non valutabile (NA)"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function criterionSourceDescription(
  criterion: ResolutionPreviewCriterion,
): string {
  if (criterion.served_by === "syllabus") {
    return "Confronto diretto tra le versioni italiana e inglese.";
  }
  if (criterion.served_by === "registry") {
    const groups = groupByChain(criterion.candidates);
    const sourceCount = groups.filter((group) => group.autoPick).length;
    return `${sourceCount} ${
      sourceCount === 1 ? "fonte documentale disponibile" : "fonti documentali disponibili"
    }.`;
  }
  const missingSource: Record<ExtendedCriterionCode, string> = {
    E1: "SUA-CdS non disponibile nel registry.",
    E2: "Matrice di Tuning non disponibile nel registry.",
    E3: "Regolamento didattico non disponibile nel registry.",
    E4: "Versione inglese del syllabus non disponibile.",
    E5: "Nessuna linea guida o uso locale disponibile nel registry.",
  };
  return missingSource[criterion.criterion_code];
}

/**
 * One row per chain in the criterion's candidate list. A chain is
 * the family of versions of the same document; each chain
 * contributes at most one document to the run (resolver
 * behaviour). The criterion's "effective perimeter" is the union
 * of the per-chain picks — overridden where the user touched the
 * radio, automatic everywhere else.
 */
interface ChainGroup {
  chainKey: string;
  candidates: ResolutionPreviewCandidate[];
  /** Resolver's pick for this chain, if any. */
  autoPick: ResolutionPreviewCandidate | undefined;
}

function groupByChain(
  candidates: ResolutionPreviewCandidate[],
): ChainGroup[] {
  // Use an insertion-ordered Map so the chain rendering follows
  // the candidates' deterministic backend order (local_document_id
  // ascending → first chain seen wins the first slot).
  const map = new Map<string, ChainGroup>();
  for (const c of candidates) {
    const existing = map.get(c.chain_key);
    if (existing) {
      existing.candidates.push(c);
      if (!existing.autoPick && c.is_auto_resolved) {
        existing.autoPick = c;
      }
    } else {
      map.set(c.chain_key, {
        chainKey: c.chain_key,
        candidates: [c],
        autoPick: c.is_auto_resolved ? c : undefined,
      });
    }
  }
  return Array.from(map.values());
}

function chainLabel(group: ChainGroup): string {
  // All candidates in the chain share document_type and the same
  // normalized title — use the first one's display title.
  const head = group.candidates[0];
  return `${head.title} · ${labelForDocumentType(head.document_type)}`;
}

function CriterionCard({
  criterion,
  customize,
  selection,
  onSelectChain,
  onResetChain,
}: {
  criterion: ResolutionPreviewCriterion;
  customize: boolean;
  selection: Record<string, number>;
  onSelectChain: (chainKey: string, docId: number) => void;
  onResetChain: (chainKey: string) => void;
}) {
  const groups = groupByChain(criterion.candidates);
  // Effective picks: per-chain override when set, otherwise the
  // chain's auto pick (when present).
  const effectivePicks = groups
    .map((g) => {
      const overrideId = selection[g.chainKey];
      if (overrideId !== undefined) {
        return g.candidates.find((c) => c.local_document_id === overrideId);
      }
      return g.autoPick;
    })
    .filter((c): c is ResolutionPreviewCandidate => c !== undefined);
  const anyOverride = groups.some((g) => selection[g.chainKey] !== undefined);

  return (
    <div
      className={
        "border px-3 py-3 text-sm " +
        (anyOverride ? "border-emerald-500/40 bg-emerald-500/5" : "bg-background")
      }
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <code className="font-mono text-[11px] font-semibold text-primary">
          {criterion.criterion_code}
        </code>
        <span className="text-sm font-medium">
          {CRITERION_LABELS[criterion.criterion_code]}
        </span>
        {groups.length > 1 ? (
          <span className="text-[10px] text-muted-foreground">
            {groups.length} fonti
          </span>
        ) : null}
      </div>

      {/* Effective perimeter — one row per chain in this criterion. */}
      <div className="mt-2">
        {criterion.served_by === "syllabus" ? (
          <p className="text-xs text-muted-foreground">
            Servito dal syllabus stesso (campi <code className="font-mono">*_en</code>).
            Nessun documento del registry partecipa.
          </p>
        ) : criterion.served_by === "none" || !criterion.applicable ? (
          <p className="text-xs text-amber-700 dark:text-amber-300">
            {criterion.na_reason ?? "Non applicabile per questo syllabus."}
          </p>
        ) : effectivePicks.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Nessun documento attualmente selezionabile.
          </p>
        ) : (
          <div className="space-y-1">
            {effectivePicks.map((c) => (
              <CandidateRow
                key={c.local_document_id}
                candidate={c}
                selected
                overrideActive={selection[c.chain_key] !== undefined}
              />
            ))}
          </div>
        )}
      </div>

      {/* Alternatives (expanded) — one radio group per chain. */}
      {customize && criterion.served_by === "registry" && criterion.applicable && (
        <ChainAlternatives
          criterion={criterion}
          groups={groups}
          selection={selection}
          onSelectChain={onSelectChain}
          onResetChain={onResetChain}
        />
      )}
    </div>
  );
}

function ChainAlternatives({
  criterion,
  groups,
  selection,
  onSelectChain,
  onResetChain,
}: {
  criterion: ResolutionPreviewCriterion;
  groups: ChainGroup[];
  selection: Record<string, number>;
  onSelectChain: (chainKey: string, docId: number) => void;
  onResetChain: (chainKey: string) => void;
}) {
  const customizableGroups = groups.filter(
    (group) =>
      group.candidates.filter((candidate) => candidate.selectable).length > 1,
  );
  if (customizableGroups.length === 0) {
    return (
      <div className="mt-2.5 border-t border-dashed border-border/60 pt-2">
        <p className="text-xs text-muted-foreground">
          Nessuna versione alternativa disponibile.
        </p>
      </div>
    );
  }
  return (
    <div className="mt-2.5 space-y-2.5 border-t border-dashed border-border/60 pt-2">
      <p className="text-[11px] font-medium text-foreground">
        Scegli la versione da usare
      </p>
      {customizableGroups.map((group) => {
        const overrideId = selection[group.chainKey];
        return (
          <div key={group.chainKey} className="space-y-1">
            <p className="text-[11px] font-medium text-foreground/80">
              {chainLabel(group)}
            </p>
            <ul className="space-y-1">
              {group.candidates.map((c) => {
                const isOverride = overrideId === c.local_document_id;
                const disabled = !c.selectable;
                return (
                  <li key={c.local_document_id}>
                    <label
                      className={
                        "flex cursor-pointer items-start gap-2 rounded-md border px-2 py-1.5 text-xs transition-colors " +
                        (disabled
                          ? "cursor-not-allowed border-border/50 bg-muted/30 text-muted-foreground"
                          : isOverride
                            ? "border-emerald-500/30 bg-emerald-500/5"
                            : "border-border hover:bg-muted/30")
                      }
                    >
                      <input
                        type="radio"
                        name={`override-${criterion.criterion_code}-${group.chainKey}`}
                        className="mt-1 h-3.5 w-3.5"
                        checked={isOverride}
                        disabled={disabled}
                        onChange={() =>
                          onSelectChain(group.chainKey, c.local_document_id)
                        }
                      />
                      <div className="min-w-0 flex-1 space-y-0.5">
                        <CandidateRow
                          candidate={c}
                          selected={false}
                          overrideActive={isOverride}
                        />
                      </div>
                    </label>
                  </li>
                );
              })}
            </ul>
            {overrideId !== undefined ? (
              <button
                type="button"
                onClick={() => onResetChain(group.chainKey)}
                className="text-[11px] font-medium text-primary hover:underline"
              >
                Ripristina la scelta automatica
              </button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function CandidateRow({
  candidate,
  selected,
  overrideActive,
}: {
  candidate: ResolutionPreviewCandidate;
  selected: boolean;
  overrideActive: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
      <span className="font-medium text-foreground/90">{candidate.title}</span>
      <span className="text-[10px] text-muted-foreground">
        {labelForDocumentType(candidate.document_type)}
      </span>
      <span className="text-[10px] tabular-nums text-muted-foreground">
        versione {candidate.version}
      </span>
      {candidate.academic_year ? (
        <span className="text-[10px] text-muted-foreground">
          A.A. {candidate.academic_year}
        </span>
      ) : null}
      {selected ? (
        overrideActive ? (
          // 9.E.3.fix: mirror the post-run pill on the pre-run
          // dialog — the user-pinned candidate gets the emerald
          // "Selezione esplicita" pill that the audit row will
          // carry once the evaluation is created.
          <ResolutionReasonPill reason="explicit_selection" />
        ) : candidate.is_auto_resolved ? (
          <ResolutionReasonPill reason={candidate.resolution_reason} />
        ) : null
      ) : null}
      {candidate.deleted_at ? (
        <span
          className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300"
          title={`Soft-delete: ${candidate.deleted_at}`}
        >
          <Archive className="h-3 w-3" aria-hidden />
          archiviato
        </span>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton + error
// ---------------------------------------------------------------------------

function PreviewSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="h-16 animate-pulse rounded-md border bg-muted/40"
          aria-hidden
        />
      ))}
    </div>
  );
}

function PreviewError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-3 text-xs text-rose-800 dark:text-rose-200">
      <p className="mb-1 font-medium uppercase tracking-wide">
        Caricamento preview fallito
      </p>
      <p className="mb-2">{message}</p>
      <Button type="button" size="sm" variant="outline" onClick={onRetry}>
        Riprova
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error-code translation
// ---------------------------------------------------------------------------

function explainValidationCode(
  code: SelectedDocumentValidationCode | undefined,
  fallback: string,
): string {
  switch (code) {
    case "duplicate":
      return "Hai selezionato lo stesso documento più di una volta.";
    case "unknown":
      return "Uno dei documenti selezionati non esiste più nel registry.";
    case "not_indexed":
      return "Uno dei documenti selezionati non è ancora completamente indicizzato.";
    case "archived":
      return "Uno dei documenti selezionati è archiviato e non può alimentare nuove valutazioni.";
    case "wrong_cdl":
      return "Uno dei documenti selezionati appartiene a un altro Corso di Studio.";
    case "no_enabled_criteria":
      return "Uno dei documenti selezionati non ha criteri estesi abilitati.";
    default:
      return fallback || "La selezione corrente non è valida.";
  }
}

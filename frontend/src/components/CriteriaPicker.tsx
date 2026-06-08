import {
  DOCUMENT_TYPES,
  allowedCriteriaFor,
  labelForDocumentType,
} from "@/data/sources";
import type {
  ExtendedCriterionCode,
  LocalDocumentType,
} from "@/lib/types";

const ALL_CRITERIA: ExtendedCriterionCode[] = ["E1", "E2", "E3", "E4", "E5"];

interface Props {
  value: ExtendedCriterionCode[];
  onChange: (next: ExtendedCriterionCode[]) => void;
  /** When set, marks the type's default criteria with a dot and
   *  surfaces them in the helper line below the chips. Also gates
   *  which chips are rendered (Phase 9.A.B): only criteria allowed
   *  for this type can be toggled. */
  defaultsFor?: LocalDocumentType;
  disabled?: boolean;
  /** Optional label rendered above the chips. */
  label?: string;
}

/**
 * Phase 9.A.B — shared E1-E5 chip toggle with document-type gating.
 *
 * When ``defaultsFor`` is passed, the picker honours the
 * ``ALLOWED_CRITERIA_BY_DOCUMENT_TYPE`` contract from Phase 9.A:
 * only criteria allowed for the type are toggleable, and types
 * registered as context-only (``piano_studi``, ``manifesto``,
 * ``propedeuticita``, ``metadati_ufficiali``) render an inline
 * note instead of an empty chip row. Without ``defaultsFor`` the
 * picker falls back to the legacy behaviour (all five chips
 * toggleable) — useful for tests / future surfaces where the type
 * isn't known up front.
 */
export function CriteriaPicker({
  value,
  onChange,
  defaultsFor,
  disabled,
  label = "Criteri estesi abilitati",
}: Props) {
  const defaults = defaultsFor
    ? DOCUMENT_TYPES.find((t) => t.code === defaultsFor)?.default_enabled ?? []
    : [];
  const allowed = defaultsFor ? allowedCriteriaFor(defaultsFor) : ALL_CRITERIA;
  const codesToRender = defaultsFor ? allowed : ALL_CRITERIA;
  const isContextOnly = defaultsFor !== undefined && allowed.length === 0;

  const toggle = (code: ExtendedCriterionCode) => {
    if (disabled) return;
    // Defensive: ignore toggles that would break the allowed
    // contract even if a caller passes a malformed `value`.
    if (defaultsFor && !allowed.includes(code)) return;
    onChange(
      value.includes(code) ? value.filter((c) => c !== code) : [...value, code],
    );
  };

  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      {isContextOnly ? (
        <div className="mt-1 rounded-md border border-dashed bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          Questo documento non alimenta automaticamente alcun criterio
          esteso. Resta tracciato nel registry come contesto.
        </div>
      ) : (
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {codesToRender.map((code) => {
            const active = value.includes(code);
            const isDefault = defaults.includes(code);
            return (
              <button
                key={code}
                type="button"
                onClick={() => toggle(code)}
                aria-pressed={active}
                disabled={disabled}
                className={
                  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[11px] font-semibold uppercase transition-colors disabled:cursor-not-allowed disabled:opacity-50 " +
                  (active
                    ? "border-amber-300 bg-amber-500/15 text-amber-900"
                    : "border-border bg-card text-muted-foreground hover:border-amber-300 hover:bg-amber-500/10 hover:text-amber-900")
                }
              >
                {code}
                {isDefault ? (
                  <span
                    aria-label="default per il tipo selezionato"
                    className="text-[8px] font-medium normal-case text-current/70"
                  >
                    •
                  </span>
                ) : null}
              </button>
            );
          })}
          {defaultsFor ? (
            <span className="ml-1 text-[10px] text-muted-foreground">
              default per «{labelForDocumentType(defaultsFor)}»:{" "}
              {defaults.join(", ") || "—"}
            </span>
          ) : null}
        </div>
      )}
    </div>
  );
}

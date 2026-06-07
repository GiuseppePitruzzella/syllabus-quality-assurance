import { DOCUMENT_TYPES, labelForDocumentType } from "@/data/sources";
import type {
  ExtendedCriterionCode,
  LocalDocumentType,
} from "@/lib/types";

const ALL_CRITERIA: ExtendedCriterionCode[] = ["E1", "E2", "E3", "E4", "E5"];

interface Props {
  value: ExtendedCriterionCode[];
  onChange: (next: ExtendedCriterionCode[]) => void;
  /** When set, marks the type's default criteria with a dot and
   *  surfaces them in the helper line below the chips. */
  defaultsFor?: LocalDocumentType;
  disabled?: boolean;
  /** Optional label rendered above the chips. */
  label?: string;
}

/**
 * Phase 8.D.C — shared E1-E5 chip toggle.
 *
 * Used by the upload modal (initial value, defaults derived from
 * document_type) and by the in-card edit affordance (current
 * server value, no defaults needed because the document already
 * has a concrete enabled_criteria list).
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
  const toggle = (code: ExtendedCriterionCode) => {
    if (disabled) return;
    onChange(
      value.includes(code) ? value.filter((c) => c !== code) : [...value, code],
    );
  };
  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        {ALL_CRITERIA.map((code) => {
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
    </div>
  );
}

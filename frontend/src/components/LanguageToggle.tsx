import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export type Lang = "it" | "en";

interface LanguageToggleProps {
  value: Lang;
  onChange: (next: Lang) => void;
  /** When false the EN button is disabled with an explanatory tooltip. */
  hasEnglish: boolean;
  /** Optional `aria-label` for screen readers. Defaults to "Lingua". */
  label?: string;
}

const COMMON_BUTTON =
  "inline-flex h-7 min-w-[3rem] items-center justify-center rounded-lg px-3 text-xs font-medium leading-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1";

const ACTIVE =
  "bg-primary text-primary-foreground shadow-sm";

const INACTIVE =
  "text-muted-foreground hover:bg-muted hover:text-foreground";

const DISABLED =
  "cursor-not-allowed text-muted-foreground/40";

/**
 * Phase 6.1.A — segmented control for the IT / ENG language switch.
 *
 * Used by `SyllabusViewer` and, in the future, anywhere the user
 * picks between the Italian and English variant of a syllabus.
 * Pure presentational: no language state of its own, no I/O.
 *
 * Accessibility:
 *   - `role="group"` + `aria-label` on the container
 *   - `aria-pressed` on each segment so screen readers announce the
 *     active state
 *   - `focus-visible` ring inherited from the rest of the design system
 *
 * The ENG button stays in the DOM when not available (instead of
 * being hidden) so the toggle width does not jump between syllabi —
 * the button is rendered as a disabled `<span>` wrapped in a
 * tooltip that explains why it can't be selected.
 */
export function LanguageToggle({
  value,
  onChange,
  hasEnglish,
  label = "Lingua",
}: LanguageToggleProps) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex h-9 items-center gap-0.5 rounded-xl border bg-card p-1"
    >
      <button
        type="button"
        onClick={() => onChange("it")}
        aria-pressed={value === "it"}
        className={`${COMMON_BUTTON} ${value === "it" ? ACTIVE : INACTIVE}`}
      >
        IT
      </button>
      {hasEnglish ? (
        <button
          type="button"
          onClick={() => onChange("en")}
          aria-pressed={value === "en"}
          className={`${COMMON_BUTTON} ${value === "en" ? ACTIVE : INACTIVE}`}
        >
          ENG
        </button>
      ) : (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger
              render={
                <span
                  aria-disabled="true"
                  className={`${COMMON_BUTTON} ${DISABLED}`}
                />
              }
            >
              ENG
            </TooltipTrigger>
            <TooltipContent>Versione inglese non disponibile</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}

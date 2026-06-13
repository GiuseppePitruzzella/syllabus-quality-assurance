import type { ResolutionReason } from "@/lib/types";

/**
 * Phase 9.E.3 — single source of truth for the resolver's
 * precedence-ladder pill.
 *
 * Centralised here so the EvaluatePreflightDialog (the *pre-run*
 * surface) and ExternalDocumentsUsed (the *post-run* surface)
 * always agree on:
 *
 *   - the palette (emerald / sky / amber);
 *   - the user-facing label (Italian, Title case);
 *   - the layout (compact pill with a coloured border + tinted
 *     background).
 *
 * Tone of voice
 *   - "Selezione esplicita" — the user pinned this version
 *     via the preflight dialog.
 *   - "Anno accademico" — the resolver matched the syllabus's
 *     academic year on this chain.
 *   - "Fallback ultima versione" — no explicit pick, no year
 *     match; the resolver fell back to the most recent version
 *     of the chain.
 */
const RESOLUTION_REASON_META: Record<
  ResolutionReason,
  { label: string; cls: string }
> = {
  explicit_selection: {
    label: "Selezione esplicita",
    cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  },
  academic_year_match: {
    label: "Anno accademico",
    cls: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  },
  latest_available_fallback: {
    label: "Fallback ultima versione",
    cls: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  },
};

/**
 * Render the resolver's reason pill.
 *
 * Accepts ``null`` so the preflight dialog can pass through the
 * payload for candidates that are not auto-resolved without an
 * explicit ``if`` guard at every call site. Returns ``null`` in
 * that case so React renders nothing.
 */
export function ResolutionReasonPill({
  reason,
}: {
  reason: ResolutionReason | null | undefined;
}) {
  if (!reason) return null;
  const meta = RESOLUTION_REASON_META[reason];
  if (!meta) return null;
  return (
    <span
      className={
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium " +
        meta.cls
      }
    >
      {meta.label}
    </span>
  );
}

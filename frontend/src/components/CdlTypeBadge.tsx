interface CdlTypeBadgeProps {
  /** Full type label, e.g. "Magistrale" / "Triennale" (Dashboard data). */
  type?: string | null;
  /** Class code, e.g. "LM-18" / "L-31" (used when `type` is unavailable). */
  code?: string | null;
}

/**
 * Compact L / LM indicator for a Corso di Studio, shared by the Dashboard
 * pickers and the Results export combo so both render CdS the same way.
 * Prefers an explicit `type`; otherwise infers the cycle from the class code.
 */
export function CdlTypeBadge({ type, code }: CdlTypeBadgeProps) {
  const isTriennale = type
    ? type.toLowerCase().includes("triennale")
    : !(code ?? "").trim().toUpperCase().startsWith("LM");
  return (
    <span
      className={`inline-flex w-8 items-center justify-center font-mono text-[11px] font-semibold uppercase tracking-wide ${
        isTriennale ? "text-emerald-700" : "text-sky-800"
      }`}
    >
      {isTriennale ? "L" : "LM"}
    </span>
  );
}

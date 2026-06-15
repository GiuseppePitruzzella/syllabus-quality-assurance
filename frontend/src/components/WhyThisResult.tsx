import type { ReactNode } from "react";

export interface WhyThisResultEvidence {
  text: string;
  sourceField: string | null;
}

export interface WhyThisResultProps {
  /** Esito */
  outcome: { score: number | null; isNa: boolean; label: string };
  /** Cosa valuta */
  whatItEvaluates: string;
  /** Motivazione */
  justification: string | null;
  /** Evidenze */
  evidences: WhyThisResultEvidence[];
  /** Limiti */
  limits?: string[];
  confidence?: "low" | "medium" | "high" | null;
  /** When true reveals technical extras (source field, confidence). */
  technical?: boolean;
}

const SCORE_BADGE: Record<string, string> = {
  // score 2 is intentionally discreet; 0/1 carry visual weight
  "2": "border-slate-300 bg-slate-100 text-slate-600",
  "1": "border-amber-400 bg-amber-100 text-amber-900 font-semibold",
  "0": "border-rose-400 bg-rose-100 text-rose-900 font-semibold",
  NA: "border-border bg-muted text-muted-foreground",
};

/** Standard result presentation: Esito → Cosa valuta → Motivazione →
 *  Evidenze → Limiti. Pure presentational; the caller supplies a
 *  normalized view-model. */
export function WhyThisResult({
  outcome,
  whatItEvaluates,
  justification,
  evidences,
  limits = [],
  confidence = null,
  technical = false,
}: WhyThisResultProps) {
  const badgeKey =
    outcome.isNa || outcome.score === null ? "NA" : String(outcome.score);

  return (
    <div className="space-y-3 text-sm">
      <Field label="Esito">
        <span className="inline-flex items-center gap-2">
          <span
            className={
              "inline-flex h-6 min-w-9 items-center justify-center rounded-md border px-1.5 text-sm font-medium " +
              SCORE_BADGE[badgeKey]
            }
          >
            {badgeKey}
          </span>
          <span>{outcome.label}</span>
        </span>
      </Field>

      <Field label="Cosa valuta">
        <p className="leading-relaxed text-muted-foreground">
          {whatItEvaluates}
        </p>
      </Field>

      {justification ? (
        <Field label="Motivazione">
          <p className="leading-relaxed">{justification}</p>
        </Field>
      ) : null}

      <Field label="Evidenze">
        {evidences.length > 0 ? (
          <ul className="space-y-1.5">
            {evidences.map((ev, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                {technical && ev.sourceField ? (
                  <code className="self-start rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    {ev.sourceField}
                  </code>
                ) : null}
                <span className="text-foreground/90">“{ev.text}”</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground">
            Nessuna citazione testuale collegata a questo criterio.
          </p>
        )}
      </Field>

      {limits.length > 0 ? (
        <Field label="Limiti">
          <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
            {limits.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </Field>
      ) : null}

      {technical && confidence ? (
        <p className="text-xs text-muted-foreground">
          Confidenza: {confidence}
        </p>
      ) : null}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}

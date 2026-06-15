import { useState, type ReactNode } from "react";

import { truncateText } from "@/lib/text";

const GUIDED_INITIAL_EVIDENCES = 2;
const MAX_EVIDENCE_CHARS = 240;

export interface WhyThisResultEvidence {
  text: string;
  sourceField: string | null;
}

export interface WhyThisResultProps {
  score: number | null;
  isNa: boolean;
  /** NA caused by a technical failure (agent error), not a semantic call. */
  isNaTechnical?: boolean;
  /** Criterion description (rubric) — shown as a subtle framing line. */
  whatItEvaluates: string;
  /** Persisted agent justification — the narrative body. */
  justification: string | null;
  evidences: WhyThisResultEvidence[];
  /** What "adequate" looks like (score-2 rubric anchor); drives the
   *  "cosa correggere/migliorare" callout for score 0/1. */
  improvementTarget?: string | null;
  naReason?: string | null;
  confidence?: "low" | "medium" | "high" | null;
  /** Technical view adds source fields + confidence. */
  technical?: boolean;
}

type Kind = "critical" | "improve" | "ok" | "na-technical" | "na";

function resolveKind(
  score: number | null,
  isNa: boolean,
  isNaTechnical: boolean,
): Kind {
  if (isNaTechnical) return "na-technical";
  if (isNa || score === null) return "na";
  if (score === 0) return "critical";
  if (score === 1) return "improve";
  return "ok";
}

const LEAD: Record<Kind, { label: string; dot: string; text: string }> = {
  critical: { label: "Criticità da correggere", dot: "bg-rose-500", text: "text-rose-900" },
  improve: { label: "Area da migliorare", dot: "bg-amber-500", text: "text-amber-900" },
  ok: { label: "Adeguato", dot: "bg-slate-400", text: "text-slate-600" },
  "na-technical": { label: "Non valutabile (problema tecnico)", dot: "bg-slate-400", text: "text-slate-600" },
  na: { label: "Non valutabile", dot: "bg-slate-400", text: "text-slate-600" },
};

const ACTION_CALLOUT: Record<"critical" | "improve", { title: string; box: string }> = {
  critical: { title: "Cosa correggere", box: "border-rose-300 bg-rose-50" },
  improve: { title: "Cosa migliorare", box: "border-amber-300 bg-amber-50" },
};

/**
 * Phase 10.A R1 (polish) — narrative explanation of one criterion.
 *
 * Deterministic composition of already-persisted data (no LLM):
 * an outcome lead, the agent justification as prose, the relevant
 * syllabus quotes, and a clear "what to fix/improve" callout for
 * score 0/1 (derived from the score-2 rubric anchor). Score 2 renders
 * compact and discreet; technical view adds source fields + confidence.
 */
export function WhyThisResult({
  score,
  isNa,
  isNaTechnical = false,
  whatItEvaluates,
  justification,
  evidences,
  improvementTarget = null,
  naReason = null,
  confidence = null,
  technical = false,
}: WhyThisResultProps) {
  const kind = resolveKind(score, isNa, isNaTechnical);
  const lead = LEAD[kind];
  const compact = kind === "ok";
  const showActionCallout =
    (kind === "critical" || kind === "improve") && !!improvementTarget;

  return (
    <div className="space-y-2.5 text-sm">
      {/* Outcome lead — guides the reading for 0/1, discreet for 2 */}
      <div className={"flex items-center gap-2 font-semibold " + lead.text}>
        <span className={"inline-block h-2 w-2 rounded-full " + lead.dot} aria-hidden />
        <span>{lead.label}</span>
      </div>

      {!compact ? (
        <p className="text-xs text-muted-foreground">Valuta: {whatItEvaluates}</p>
      ) : null}

      {justification ? (
        <p className="leading-relaxed">{justification}</p>
      ) : null}

      {kind === "na-technical" ? (
        <p className="text-muted-foreground">
          Il criterio non è stato valutato per un problema tecnico dell'agente.
        </p>
      ) : null}

      {kind === "na" && naReason ? (
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">Perché non valutabile: </span>
          {naReason}
        </p>
      ) : null}

      <Evidences evidences={evidences} technical={technical} compact={compact} />

      {showActionCallout ? (
        <div
          className={
            "rounded-md border-l-2 px-3 py-2 " +
            ACTION_CALLOUT[kind as "critical" | "improve"].box
          }
        >
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {ACTION_CALLOUT[kind as "critical" | "improve"].title}
          </p>
          <p className="mt-0.5 leading-relaxed">{improvementTarget}</p>
        </div>
      ) : null}

      {technical && confidence ? (
        <p className="text-xs text-muted-foreground">Confidenza: {confidence}</p>
      ) : null}
    </div>
  );
}

function Evidences({
  evidences,
  technical,
  compact,
}: {
  evidences: WhyThisResultEvidence[];
  technical: boolean;
  compact: boolean;
}) {
  // Local state persists across refetch while the row stays expanded.
  const [showAll, setShowAll] = useState(false);
  const [expandedQuotes, setExpandedQuotes] = useState<Set<number>>(new Set());

  // Discreet score-2 rows omit the empty-state message entirely.
  if (evidences.length === 0) {
    if (compact) return null;
    return (
      <p className="text-xs text-muted-foreground">
        Nessuna citazione testuale collegata a questo criterio.
      </p>
    );
  }

  // Technical: every evidence, full text, source fields, no truncation.
  if (technical) {
    return (
      <Block label="Dal syllabus">
        <ul className="space-y-1.5">
          {evidences.map((ev, i) => (
            <li key={i} className="flex flex-col gap-0.5">
              {ev.sourceField ? (
                <code className="self-start rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  {ev.sourceField}
                </code>
              ) : null}
              <Quote text={ev.text} />
            </li>
          ))}
        </ul>
      </Block>
    );
  }

  // Guided: keep evidences in persisted order; show max 2, each ≤240
  // chars, with per-quote and per-list expansion.
  const visible = showAll
    ? evidences
    : evidences.slice(0, GUIDED_INITIAL_EVIDENCES);
  const remaining = evidences.length - GUIDED_INITIAL_EVIDENCES;

  const toggleQuote = (i: number) =>
    setExpandedQuotes((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  return (
    <Block label="Dal syllabus">
      <ul className="space-y-2">
        {visible.map((ev, i) => {
          const open = expandedQuotes.has(i);
          const { text, truncated } = truncateText(ev.text, MAX_EVIDENCE_CHARS);
          const display = open || !truncated ? ev.text : text;
          return (
            <li key={i} className="flex flex-col gap-0.5">
              <Quote text={display} />
              {truncated ? (
                <button
                  type="button"
                  onClick={() => toggleQuote(i)}
                  className="self-start text-xs font-medium text-primary hover:underline"
                >
                  {open ? "Mostra meno" : "Mostra testo completo"}
                </button>
              ) : null}
            </li>
          );
        })}
      </ul>
      {!showAll && remaining > 0 ? (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="mt-1.5 text-xs font-medium text-primary hover:underline"
        >
          Mostra altre {remaining} {remaining === 1 ? "evidenza" : "evidenze"}
        </button>
      ) : null}
      {showAll && evidences.length > GUIDED_INITIAL_EVIDENCES ? (
        <button
          type="button"
          onClick={() => setShowAll(false)}
          className="mt-1.5 text-xs font-medium text-primary hover:underline"
        >
          Mostra meno evidenze
        </button>
      ) : null}
    </Block>
  );
}

function Quote({ text }: { text: string }) {
  return (
    <span className="border-l-2 border-muted-foreground/20 pl-2 text-foreground/90">
      “{text}”
    </span>
  );
}

function Block({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}

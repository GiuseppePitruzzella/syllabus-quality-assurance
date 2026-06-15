import type { EvaluationStatus } from "@/lib/types";

export interface Term {
  plain: string;
  technical?: string;
}

/** Technical terms translated to plain Italian; the original is kept
 *  in parentheses by `withTechnical` when useful. Values are phrases,
 *  not isolated words (e.g. `resolver`). */
export const COMPREHENSION_TERMS: Record<string, Term> = {
  coverage: { plain: "copertura", technical: "coverage" },
  core_score: { plain: "punteggio core", technical: "CoreScore" },
  rag: { plain: "recupero dal corpus normativo", technical: "RAG" },
  embedding: { plain: "rappresentazione vettoriale", technical: "embedding" },
  prompt_version: { plain: "versione del prompt", technical: "prompt version" },
  chunk: { plain: "frammento di testo", technical: "chunk" },
  hash: { plain: "impronta del file", technical: "hash" },
  resolver: {
    plain: "Selezione automatica delle fonti",
    technical: "resolver",
  },
};

export const AGENT_LABELS: Record<string, string> = {
  A1: "Completezza",
  A2: "Risultati di apprendimento",
  A3: "Coerenza didattica",
  A4: "Cura editoriale",
  A5: "Allineamento documentale (esteso)",
};

export const STATUS_LABELS: Record<EvaluationStatus, string> = {
  pending: "In coda",
  running: "In corso",
  completed: "Completata",
  partial: "Completata parzialmente",
  failed: "Non riuscita",
};

export const CONFIDENCE_LABELS: Record<string, string> = {
  low: "bassa",
  medium: "media",
  high: "alta",
};

export const SCORE_MEANINGS: Record<string, string> = {
  "0": "criticità",
  "1": "da migliorare",
  "2": "adeguato",
  NA: "non valutabile",
};

/** Readable label for a technical term key; falls back to the key. */
export function plain(key: string): string {
  return COMPREHENSION_TERMS[key]?.plain ?? key;
}

/** Readable label with the original term in parentheses when defined. */
export function withTechnical(key: string): string {
  const term = COMPREHENSION_TERMS[key];
  if (!term) return key;
  return term.technical ? `${term.plain} (${term.technical})` : term.plain;
}

import type { EvaluationStatus } from "@/lib/types";

/** Canonical core criteria; the verdict ignores any other key. */
export const CORE_CRITERION_CODES = [
  "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
] as const;

export const TOTAL_CORE_CRITERIA = CORE_CRITERION_CODES.length; // 9

const INCONSISTENCY_TOLERANCE = 0.05;

export interface VerdictInput {
  status: EvaluationStatus;
  coreScore: number | null;
  coverage: number | null;
  criterionScores: Record<string, number | null> | null;
}

export type VerdictBand =
  | "ottima"
  | "buona"
  | "discreta"
  | "da_rivedere"
  | "copertura_insufficiente"
  | "non_disponibile";

export type VerdictTone = "positive" | "neutral" | "attention" | "muted";

export interface VerdictChip {
  label: string;
  tone: "critical" | "warning" | "muted";
}

export interface Verdict {
  band: VerdictBand;
  headline: string;
  tone: VerdictTone;
  criticalCount: number;
  improvableCount: number;
  evaluatedCount: number;
  naCount: number;
  totalCount: number;
  computedCoreScore: number | null;
  coverageSufficient: boolean;
  partialCoverage: boolean;
  partialExecution: boolean;
  chips: VerdictChip[];
  inconsistent: boolean;
}

function buildChips(args: {
  criticalCount: number;
  improvableCount: number;
  naCount: number;
}): VerdictChip[] {
  const { criticalCount, improvableCount, naCount } = args;
  const chips: VerdictChip[] = [];
  if (criticalCount > 0) {
    // "criticità" is invariant in Italian (1 criticità / 2 criticità)
    chips.push({ label: `${criticalCount} criticità`, tone: "critical" });
  }
  if (improvableCount > 0) {
    chips.push({
      label:
        improvableCount === 1
          ? "1 area da migliorare"
          : `${improvableCount} aree da migliorare`,
      tone: "warning",
    });
  }
  if (naCount > 0) {
    chips.push({
      label:
        naCount === 1
          ? "1 criterio non valutabile"
          : `${naCount} criteri non valutabili`,
      tone: "muted",
    });
  }
  return chips;
}

export function computeVerdict(input: VerdictInput): Verdict {
  const { status, coreScore, coverage, criterionScores } = input;

  // --- counts over canonical C1..C9 keys only ---
  let criticalCount = 0;
  let improvableCount = 0;
  let evaluatedCount = 0;
  let sum = 0;
  let inconsistent = false;

  for (const code of CORE_CRITERION_CODES) {
    const raw = criterionScores ? criterionScores[code] : undefined;
    if (raw === undefined || raw === null) {
      continue; // missing key or explicit null => NA
    }
    if (raw === 0 || raw === 1 || raw === 2) {
      evaluatedCount += 1;
      sum += raw;
      if (raw === 0) criticalCount += 1;
      else if (raw === 1) improvableCount += 1;
    } else {
      inconsistent = true; // out-of-domain value => NA + flag
    }
  }

  const totalCount = TOTAL_CORE_CRITERIA;
  const naCount = totalCount - evaluatedCount;
  const computedCoreScore = evaluatedCount > 0 ? sum / evaluatedCount : null;
  // >= 2/3 via integer cross-multiplication (no float compare)
  const coverageSufficient = evaluatedCount * 3 >= totalCount * 2;
  const partialExecution = status === "partial";

  // --- defensive checks (do NOT affect band) ---
  if (
    computedCoreScore !== null &&
    coreScore !== null &&
    Math.abs(computedCoreScore - coreScore) > INCONSISTENCY_TOLERANCE
  ) {
    inconsistent = true;
  }
  if (coverage !== null) {
    const computedCoverage = evaluatedCount / totalCount;
    if (Math.abs(computedCoverage - coverage) > INCONSISTENCY_TOLERANCE) {
      inconsistent = true;
    }
  }

  const base = {
    criticalCount,
    improvableCount,
    evaluatedCount,
    naCount,
    totalCount,
    computedCoreScore,
    coverageSufficient,
    partialExecution,
    inconsistent,
  };

  // --- failed run ---
  if (status === "failed") {
    return {
      ...base,
      band: "non_disponibile",
      headline: "Valutazione non riuscita",
      tone: "muted",
      partialCoverage: false,
      chips: [],
    };
  }

  // --- not yet available ---
  if (
    status === "pending" ||
    status === "running" ||
    criterionScores === null ||
    criterionScores === undefined
  ) {
    return {
      ...base,
      band: "non_disponibile",
      headline: "Punteggi non ancora disponibili",
      tone: "muted",
      partialCoverage: false,
      chips: [],
    };
  }

  // --- coverage insufficient ---
  if (!coverageSufficient) {
    return {
      ...base,
      band: "copertura_insufficiente",
      headline:
        "Copertura insufficiente per formulare un giudizio complessivo affidabile",
      tone: "attention",
      partialCoverage: false,
      chips: buildChips({ criticalCount, improvableCount, naCount }),
    };
  }

  // --- evaluable: band from computedCoreScore (non-null when sufficient) ---
  const score = computedCoreScore as number;
  let band: VerdictBand;
  if (score >= 1.8) band = "ottima";
  else if (score >= 1.4) band = "buona";
  else if (score >= 1.0) band = "discreta";
  else band = "da_rivedere";

  // cap (future-weights guard): a criticità caps the band at "buona".
  // With 9 equal weights one zero already prevents 1.8, so this is a no-op today.
  if (criticalCount > 0 && band === "ottima") {
    band = "buona";
  }

  const headline =
    band === "da_rivedere"
      ? "Qualità da rivedere"
      : `Qualità complessivamente ${band}`;

  const tone: VerdictTone =
    band === "da_rivedere" || criticalCount > 0
      ? "attention"
      : band === "discreta"
        ? "neutral"
        : "positive";

  return {
    ...base,
    band,
    headline,
    tone,
    partialCoverage: evaluatedCount < totalCount,
    chips: buildChips({ criticalCount, improvableCount, naCount }),
  };
}

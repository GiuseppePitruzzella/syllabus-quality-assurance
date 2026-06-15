import { describe, it, expect } from "vitest";
import {
  computeVerdict,
  defaultExpandedCriteria,
  verdictSummarySentence,
} from "./verdict";
import type { VerdictInput, CriterionExpandInput } from "./verdict";

/** Build a C1..C9 score map from a 9-length array; `null` = NA. */
function scores(values: (number | null)[]): Record<string, number | null> {
  const out: Record<string, number | null> = {};
  values.forEach((v, i) => {
    out[`C${i + 1}`] = v;
  });
  return out;
}

function input(partial: Partial<VerdictInput>): VerdictInput {
  return {
    status: "completed",
    coreScore: null,
    coverage: null,
    criterionScores: null,
    ...partial,
  };
}

describe("computeVerdict — bands from computedCoreScore", () => {
  it("all 2s → ottima", () => {
    const v = computeVerdict(input({ criterionScores: scores([2, 2, 2, 2, 2, 2, 2, 2, 2]) }));
    expect(v.band).toBe("ottima");
    expect(v.computedCoreScore).toBe(2);
    expect(v.headline).toBe("Qualità complessivamente ottima");
    expect(v.chips).toEqual([]);
    expect(v.tone).toBe("positive");
  });

  it("mix averaging ~1.4 → buona", () => {
    // six 2s + three 1s = 15/9 = 1.667 → buona
    const v = computeVerdict(input({ criterionScores: scores([2, 2, 2, 2, 2, 2, 1, 1, 1]) }));
    expect(v.band).toBe("buona");
    expect(v.headline).toBe("Qualità complessivamente buona");
  });

  it("averaging ~1.1 → discreta", () => {
    // one 2 + eight 1s = 10/9 = 1.111 → discreta
    const v = computeVerdict(input({ criterionScores: scores([2, 1, 1, 1, 1, 1, 1, 1, 1]) }));
    expect(v.band).toBe("discreta");
    expect(v.headline).toBe("Qualità complessivamente discreta");
    expect(v.tone).toBe("neutral");
  });

  it("averaging < 1.0 → da_rivedere", () => {
    // three 1s + six 0s = 3/9 = 0.333
    const v = computeVerdict(input({ criterionScores: scores([1, 1, 1, 0, 0, 0, 0, 0, 0]) }));
    expect(v.band).toBe("da_rivedere");
    expect(v.headline).toBe("Qualità da rivedere");
    expect(v.tone).toBe("attention");
  });
});

describe("computeVerdict — cap is a future guard, band derives from scores", () => {
  it("eight 2s + one 0 stays buona (cannot reach ottima from scores)", () => {
    // 16/9 = 1.778 < 1.8 → buona naturally; criticalCount=1
    const v = computeVerdict(
      input({ criterionScores: scores([2, 2, 2, 2, 2, 2, 2, 2, 0]), coreScore: 1.9 }),
    );
    expect(v.band).toBe("buona");
    expect(v.criticalCount).toBe(1);
    // incoherent received coreScore must NOT override the score-derived band
    expect(v.inconsistent).toBe(true);
  });
});

describe("computeVerdict — coverage threshold (integer comparison)", () => {
  it("exactly 6/9 evaluated → sufficient, partialCoverage", () => {
    const v = computeVerdict(input({ criterionScores: scores([2, 2, 2, 2, 2, 2, null, null, null]) }));
    expect(v.coverageSufficient).toBe(true);
    expect(v.partialCoverage).toBe(true);
    expect(v.evaluatedCount).toBe(6);
    expect(v.naCount).toBe(3);
    expect(v.band).toBe("ottima");
    expect(v.chips).toEqual([{ label: "3 criteri non valutabili", tone: "muted" }]);
  });

  it("5/9 evaluated → copertura_insufficiente", () => {
    const v = computeVerdict(input({ criterionScores: scores([2, 2, 2, 2, 2, null, null, null, null]) }));
    expect(v.coverageSufficient).toBe(false);
    expect(v.band).toBe("copertura_insufficiente");
    expect(v.headline).toBe(
      "Copertura insufficiente per formulare un giudizio complessivo affidabile",
    );
  });

  it("all NA → copertura_insufficiente, no crash, computedCoreScore null", () => {
    const v = computeVerdict(input({ criterionScores: scores([null, null, null, null, null, null, null, null, null]) }));
    expect(v.band).toBe("copertura_insufficiente");
    expect(v.computedCoreScore).toBeNull();
    expect(v.evaluatedCount).toBe(0);
  });
});

describe("computeVerdict — canonical keys only", () => {
  it("ignores extra keys outside C1..C9", () => {
    const map = scores([2, 2, 2, 2, 2, 2, 2, 2, 2]);
    map["C10"] = 0;
    map["foo"] = 0;
    const v = computeVerdict(input({ criterionScores: map }));
    expect(v.evaluatedCount).toBe(9);
    expect(v.criticalCount).toBe(0);
  });

  it("treats a missing C1..C9 key as NA", () => {
    const map = scores([2, 2, 2, 2, 2, 2, 2, 2, 2]);
    delete map["C9"];
    const v = computeVerdict(input({ criterionScores: map }));
    expect(v.evaluatedCount).toBe(8);
    expect(v.naCount).toBe(1);
  });

  it("treats out-of-domain score as NA and flags inconsistent", () => {
    const map = scores([5, 2, 2, 2, 2, 2, 2, 2, 2]);
    const v = computeVerdict(input({ criterionScores: map }));
    expect(v.inconsistent).toBe(true);
    expect(v.evaluatedCount).toBe(8);
  });
});

describe("computeVerdict — defensive consistency", () => {
  it("flags inconsistent coreScore but keeps score-derived verdict", () => {
    const v = computeVerdict(
      input({ criterionScores: scores([2, 2, 2, 2, 2, 2, 2, 2, 2]), coreScore: 0.5 }),
    );
    expect(v.inconsistent).toBe(true);
    expect(v.band).toBe("ottima");
    expect(v.computedCoreScore).toBe(2);
  });

  it("flags inconsistent coverage", () => {
    const v = computeVerdict(
      input({ criterionScores: scores([2, 2, 2, 2, 2, 2, 2, 2, 2]), coverage: 0.2 }),
    );
    expect(v.inconsistent).toBe(true);
  });

  it("does not flag when coreScore matches within tolerance", () => {
    const v = computeVerdict(
      input({ criterionScores: scores([2, 2, 2, 2, 2, 2, 2, 2, 2]), coreScore: 2, coverage: 1 }),
    );
    expect(v.inconsistent).toBe(false);
  });
});

describe("computeVerdict — status branches", () => {
  it("failed → non_disponibile", () => {
    const v = computeVerdict(input({ status: "failed", criterionScores: scores([2, 2, 2, 2, 2, 2, 2, 2, 2]) }));
    expect(v.band).toBe("non_disponibile");
    expect(v.headline).toBe("Valutazione non riuscita");
    expect(v.tone).toBe("muted");
    expect(v.chips).toEqual([]);
  });

  it("pending → non_disponibile (punteggi non disponibili)", () => {
    const v = computeVerdict(input({ status: "pending" }));
    expect(v.band).toBe("non_disponibile");
    expect(v.headline).toBe("Punteggi non ancora disponibili");
  });

  it("null criterionScores → non_disponibile", () => {
    const v = computeVerdict(input({ status: "completed", criterionScores: null }));
    expect(v.band).toBe("non_disponibile");
    expect(v.headline).toBe("Punteggi non ancora disponibili");
  });

  it("partial → partialExecution true, band from scores", () => {
    const v = computeVerdict(input({ status: "partial", criterionScores: scores([2, 2, 2, 2, 2, 2, 2, 2, 2]) }));
    expect(v.partialExecution).toBe(true);
    expect(v.band).toBe("ottima");
  });
});

function scoresVerdict(values: (number | null)[]): VerdictInput {
  return {
    status: "completed",
    coreScore: null,
    coverage: null,
    criterionScores: scores(values),
  };
}

describe("verdictSummarySentence", () => {
  it("buona with three improvable → adeguato + aree da migliorare", () => {
    const v = computeVerdict(scoresVerdict([1, 1, 2, 2, 2, 2, 2, 2, 1]));
    expect(v.band).toBe("buona");
    expect(verdictSummarySentence(v)).toBe(
      "Il syllabus è generalmente adeguato, ma presenta 3 aree da migliorare.",
    );
  });

  it("ottima with no issues → no clause", () => {
    const v = computeVerdict(scoresVerdict([2, 2, 2, 2, 2, 2, 2, 2, 2]));
    expect(v.band).toBe("ottima");
    expect(verdictSummarySentence(v)).toBe(
      "Il syllabus è di qualità eccellente sui criteri valutati.",
    );
  });

  it("da_rivedere lists issues with a colon", () => {
    const v = computeVerdict(scoresVerdict([0, 0, 0, 0, 0, 0, 0, 1, 2]));
    expect(v.band).toBe("da_rivedere");
    expect(v.criticalCount).toBe(7);
    expect(verdictSummarySentence(v)).toBe(
      "Il syllabus richiede una revisione sostanziale: 7 criticità e 1 area da migliorare.",
    );
  });

  it("returns null for insufficient coverage / non disponibile", () => {
    expect(
      verdictSummarySentence(computeVerdict(scoresVerdict([2, 2, 2, 2, 2, null, null, null, null]))),
    ).toBeNull();
    expect(
      verdictSummarySentence(computeVerdict({ status: "failed", coreScore: null, coverage: null, criterionScores: null })),
    ).toBeNull();
  });
});

function expandItem(
  p: Partial<CriterionExpandInput> & { code: string },
): CriterionExpandInput {
  return { score: null, isNaTechnical: false, hasJustification: false, ...p };
}

describe("defaultExpandedCriteria — auto-expand rules", () => {
  it("expands 0 and 1, collapses 2", () => {
    const out = defaultExpandedCriteria([
      expandItem({ code: "C1", score: 0 }),
      expandItem({ code: "C2", score: 1 }),
      expandItem({ code: "C3", score: 2 }),
    ]);
    expect(out).toEqual(["C1", "C2"]);
  });

  it("expands technical NA, collapses semantic NA without justification", () => {
    const out = defaultExpandedCriteria([
      expandItem({ code: "C1", score: null, isNaTechnical: true }),
      expandItem({ code: "C2", score: null, isNaTechnical: false, hasJustification: false }),
    ]);
    expect(out).toEqual(["C1"]);
  });

  it("expands semantic NA when a useful justification exists", () => {
    const out = defaultExpandedCriteria([
      expandItem({ code: "C1", score: null, hasJustification: true }),
    ]);
    expect(out).toEqual(["C1"]);
  });

  it("handles empty list", () => {
    expect(defaultExpandedCriteria([])).toEqual([]);
  });
});

describe("computeVerdict — two-level chips and Italian plurals", () => {
  it("one criticità + two aree + one NA, singular/plural", () => {
    // C1=0 (criticità), C2=1 & C3=1 (aree), C4..C8=2, C9=null (NA)
    const v = computeVerdict(input({ criterionScores: scores([0, 1, 1, 2, 2, 2, 2, 2, null]) }));
    expect(v.criticalCount).toBe(1);
    expect(v.improvableCount).toBe(2);
    expect(v.naCount).toBe(1);
    expect(v.chips).toEqual([
      { label: "1 criticità", tone: "critical" },
      { label: "2 aree da migliorare", tone: "warning" },
      { label: "1 criterio non valutabile", tone: "muted" },
    ]);
  });

  it("two criticità + one area, plural criticità / singular area", () => {
    const v = computeVerdict(input({ criterionScores: scores([0, 0, 1, 2, 2, 2, 2, 2, 2]) }));
    expect(v.chips).toEqual([
      { label: "2 criticità", tone: "critical" },
      { label: "1 area da migliorare", tone: "warning" },
    ]);
  });
});

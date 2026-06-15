import { describe, it, expect } from "vitest";
import { plain, withTechnical, AGENT_LABELS, SCORE_MEANINGS } from "./comprehension";

describe("comprehension helpers", () => {
  it("plain() returns the readable label", () => {
    expect(plain("coverage")).toBe("copertura");
  });

  it("withTechnical() appends the original term in parentheses", () => {
    expect(withTechnical("coverage")).toBe("copertura (coverage)");
  });

  it("translates resolver as a full phrase, not a single word", () => {
    expect(withTechnical("resolver")).toBe(
      "Selezione automatica delle fonti (resolver)",
    );
  });

  it("falls back to the key when unknown", () => {
    expect(plain("zzz-unknown")).toBe("zzz-unknown");
    expect(withTechnical("zzz-unknown")).toBe("zzz-unknown");
  });

  it("exposes agent and score labels", () => {
    expect(AGENT_LABELS.A5).toBe("Allineamento documentale (esteso)");
    expect(SCORE_MEANINGS["0"]).toBe("criticità");
    expect(SCORE_MEANINGS.NA).toBe("non valutabile");
  });
});

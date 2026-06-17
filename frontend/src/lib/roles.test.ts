import { describe, expect, it } from "vitest";

import {
  REGISTERABLE_ROLE_OPTIONS,
  hasAutomaticTechnicalView,
  roleLabel,
} from "./roles";

describe("role helpers", () => {
  it("keeps admin out of public registration choices", () => {
    expect(REGISTERABLE_ROLE_OPTIONS.map((option) => option.value)).toEqual([
      "quality_reviewer",
      "technical_reviewer",
    ]);
  });

  it("enables technical view only for technical roles", () => {
    expect(hasAutomaticTechnicalView("admin")).toBe(true);
    expect(hasAutomaticTechnicalView("technical_reviewer")).toBe(true);
    expect(hasAutomaticTechnicalView("quality_reviewer")).toBe(false);
  });

  it("maps role labels to readable Italian names", () => {
    expect(roleLabel("quality_reviewer")).toBe("Revisore qualità");
    expect(roleLabel("technical_reviewer")).toBe("Revisore tecnico");
    expect(roleLabel("admin")).toBe("Amministratore");
  });
});

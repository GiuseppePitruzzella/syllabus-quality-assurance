import { describe, it, expect } from "vitest";
import { truncateText } from "./text";

describe("truncateText", () => {
  it("short text → not truncated, unchanged", () => {
    const out = truncateText("Testo breve", 240);
    expect(out.truncated).toBe(false);
    expect(out.text).toBe("Testo breve");
  });

  it("text exactly at max → not truncated", () => {
    const out = truncateText("x".repeat(240), 240);
    expect(out.truncated).toBe(false);
  });

  it("cuts at a sentence boundary when available", () => {
    const text = "A".repeat(150) + ". " + "B".repeat(200);
    const out = truncateText(text, 240);
    expect(out.truncated).toBe(true);
    expect(out.text.endsWith(".")).toBe(true);
    expect(out.text.length).toBeLessThanOrEqual(240);
    expect(out.text).toBe("A".repeat(150) + ".");
  });

  it("hard fallback at word boundary with ellipsis when no sentence end", () => {
    const text = "parola ".repeat(60).trim(); // ~419 chars, spaces only
    const out = truncateText(text, 240);
    expect(out.truncated).toBe(true);
    expect(out.text.endsWith("…")).toBe(true);
    expect(out.text.length).toBeLessThanOrEqual(241);
  });

  it("hard cut with no spaces and no boundary", () => {
    const out = truncateText("x".repeat(300), 240);
    expect(out.truncated).toBe(true);
    expect(out.text).toBe("x".repeat(240) + "…");
  });
});

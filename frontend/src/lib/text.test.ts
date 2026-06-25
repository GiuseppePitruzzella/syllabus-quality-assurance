import { describe, it, expect } from "vitest";
import {
  cleanSyllabusDisplayText,
  syllabusProseParagraphs,
  truncateText,
} from "./text";

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

describe("cleanSyllabusDisplayText", () => {
  it("removes standalone punctuation artefact lines", () => {
    expect(
      cleanSyllabusDisplayText(
        ".\nLo studente acquisisce capacità metodologiche.\n.\nSecondo periodo.",
      ),
    ).toBe(
      "Lo studente acquisisce capacità metodologiche.\nSecondo periodo.",
    );
  });

  it("preserves punctuation inside real prose", () => {
    expect(
      cleanSyllabusDisplayText(
        "Lo studente acquisisce competenze, abilità e autonomia. Esempio: laboratorio.",
      ),
    ).toBe(
      "Lo studente acquisisce competenze, abilità e autonomia. Esempio: laboratorio.",
    );
  });

  it("returns empty string for nullish values", () => {
    expect(cleanSyllabusDisplayText(null)).toBe("");
    expect(cleanSyllabusDisplayText(undefined)).toBe("");
  });
});

describe("syllabusProseParagraphs", () => {
  it("recomposes soft line breaks and one-letter word fragments", () => {
    expect(
      syllabusProseParagraphs(
        "Si utilizzano nozioni di base di a\nnalisi matematica, m\natematica discreta e p\nrogrammazione.",
      ),
    ).toEqual([
      "Si utilizzano nozioni di base di analisi matematica, matematica discreta e programmazione.",
    ]);
  });

  it("preserves paragraph boundaries after complete sentences", () => {
    expect(
      syllabusProseParagraphs(
        "Le lezioni includono attività di laboratorio.\nQualora il corso fosse erogato a distanza, il programma resterà invariato.",
      ),
    ).toEqual([
      "Le lezioni includono attività di laboratorio.",
      "Qualora il corso fosse erogato a distanza, il programma resterà invariato.",
    ]);
  });

  it("keeps numbered and bulleted entries on one readable line", () => {
    expect(
      syllabusProseParagraphs(
        "1.\nPrimo riferimento.\n2.\nSecondo riferimento.\n·\n18-23: padronanza minima.\n·\n24-27: buona padronanza.",
      ),
    ).toEqual([
      "1. Primo riferimento.",
      "2. Secondo riferimento.",
      "• 18-23: padronanza minima.",
      "• 24-27: buona padronanza.",
    ]);
  });

  it("joins split URLs and removes standalone punctuation artefacts", () => {
    expect(
      syllabusProseParagraphs(
        ".\nMateriale disponibile sul sito (\nhttps://example.test/\n) e sul canale del corso.",
      ),
    ).toEqual([
      "Materiale disponibile sul sito (https://example.test/) e sul canale del corso.",
    ]);
  });

  it("returns no paragraphs for nullish input", () => {
    expect(syllabusProseParagraphs(null)).toEqual([]);
    expect(syllabusProseParagraphs(undefined)).toEqual([]);
  });
});

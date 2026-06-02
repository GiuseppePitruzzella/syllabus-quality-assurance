import type { SyllabusDetail } from "@/lib/types";

interface DublinDescriptorsProps {
  data: SyllabusDetail;
  lang: "it" | "en";
}

const descriptors = [
  {
    key: "dublin_knowledge",
    it: "Conoscenza e comprensione",
    en: "Knowledge and understanding",
  },
  {
    key: "dublin_applying",
    it: "Capacità di applicare",
    en: "Applying knowledge",
  },
  {
    key: "dublin_judgement",
    it: "Autonomia di giudizio",
    en: "Making judgements",
  },
  {
    key: "dublin_communication",
    it: "Abilità comunicative",
    en: "Communication skills",
  },
  {
    key: "dublin_learning",
    it: "Capacità di apprendimento",
    en: "Learning skills",
  },
];

/**
 * Phase 5.9.B — restyle from shadcn Card stack to thin-bordered grid.
 *
 * Layout collapses to a single full-width card when the syllabus
 * doesn't have Dublin descriptors split out (the common SmartEdu EN
 * case where ``learning_outcomes_*`` carries a narrative paragraph
 * instead of the 5 labeled blocks).
 */
export function DublinDescriptors({ data, lang }: DublinDescriptorsProps) {
  const learningOutcomesKey = `learning_outcomes_${lang}` as keyof SyllabusDetail;
  const learningOutcomes = data[learningOutcomesKey] as string | null;
  const hasDescriptorText = descriptors.some((d) => {
    const fieldKey = `${d.key}_${lang}` as keyof SyllabusDetail;
    return Boolean((data[fieldKey] as string | null)?.trim());
  });

  if (!hasDescriptorText && learningOutcomes?.trim()) {
    return (
      <article className="rounded-lg border bg-card p-4">
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {lang === "it"
            ? "Risultati di apprendimento"
            : "Expected learning outcomes"}
        </h3>
        <p className="whitespace-pre-line text-sm leading-relaxed text-foreground/90">
          {learningOutcomes}
        </p>
      </article>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {descriptors.map((d) => {
        const fieldKey = `${d.key}_${lang}` as keyof SyllabusDetail;
        const value = (data[fieldKey] as string | null) || "";
        const hasValue = Boolean(value.trim());
        return (
          <article
            key={d.key}
            className="rounded-md border bg-card p-3"
          >
            <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {d[lang]}
            </h3>
            <p
              className={
                "whitespace-pre-line text-sm leading-relaxed " +
                (hasValue ? "text-foreground/90" : "text-muted-foreground")
              }
            >
              {value || "—"}
            </p>
          </article>
        );
      })}
    </div>
  );
}

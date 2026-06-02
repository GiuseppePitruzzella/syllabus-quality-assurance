import { Card, CardContent } from "@/components/ui/card";
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
    it: "Capacita di applicare",
    en: "Applying knowledge",
  },
  {
    key: "dublin_judgement",
    it: "Autonomia di giudizio",
    en: "Making judgements",
  },
  {
    key: "dublin_communication",
    it: "Abilita comunicative",
    en: "Communication skills",
  },
  {
    key: "dublin_learning",
    it: "Capacita di apprendimento",
    en: "Learning skills",
  },
];

export function DublinDescriptors({ data, lang }: DublinDescriptorsProps) {
  const learningOutcomesKey = `learning_outcomes_${lang}` as keyof SyllabusDetail;
  const learningOutcomes = data[learningOutcomesKey] as string | null;
  const hasDescriptorText = descriptors.some((d) => {
    const fieldKey = `${d.key}_${lang}` as keyof SyllabusDetail;
    return Boolean((data[fieldKey] as string | null)?.trim());
  });

  if (!hasDescriptorText && learningOutcomes?.trim()) {
    return (
      <Card>
        <CardContent>
          <p className="text-accent font-medium mb-2">
            {lang === "it" ? "Risultati di apprendimento" : "Expected learning outcomes"}
          </p>
          <p className="text-muted-foreground whitespace-pre-line">
            {learningOutcomes}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {descriptors.map((d) => {
        const fieldKey = `${d.key}_${lang}` as keyof SyllabusDetail;
        const value = data[fieldKey] as string | null;
        return (
          <Card key={d.key}>
            <CardContent>
              <p className="text-accent font-medium mb-2">{d[lang]}</p>
              <p className="text-muted-foreground whitespace-pre-line">
                {value || "\u2014"}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

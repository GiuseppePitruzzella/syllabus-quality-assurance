import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info, MessageSquareText } from "lucide-react";

import { CORE_CRITERIA } from "@/data/rubric";
import { useTechnicalView } from "@/context/technicalView";
import { getSyllabus } from "@/lib/api";
import { syllabusProseParagraphs } from "@/lib/text";
import type {
  CriterionJudgmentDump,
  EvaluationDetail,
  SyllabusDetail,
} from "@/lib/types";

import { EvaluationSection } from "./EvaluationSection";
import { ReportMarkdown } from "./EvaluationReport";

interface Props {
  data: EvaluationDetail;
}

type AnnotationTone = "critical" | "improvable";

interface SectionAnnotation {
  code: string;
  name: string;
  score: 0 | 1;
  tone: AnnotationTone;
  justification: string | null;
  evidence: string | null;
  sourceFields: string[];
}

interface SyllabusSection {
  id: string;
  title: string;
  fields: string[];
  body?: string;
  paragraphs?: Array<{ label: string; text: string }>;
  schedule?: SyllabusDetail["schedule_it"];
}

const criterionMeta = new Map(CORE_CRITERIA.map((criterion) => [
  criterion.code,
  criterion,
]));

const FALLBACK_SECTION_CRITERIA: Record<string, string[]> = {
  outcomes: ["C2", "C3", "C4"],
  teaching_methods: ["C1"],
  prerequisites: ["C5"],
  attendance: ["C1"],
  content: ["C6", "C7"],
  references: ["C9"],
  schedule: ["C7"],
  assessment: ["C8"],
  sample_questions: ["C8"],
};

/**
 * Phase 13 — annotated syllabus reading surface.
 *
 * The component reconstructs the original syllabus as an academic
 * document and overlays deterministic annotations from the persisted
 * C1-C9 judgments. It does NOT ask the LLM to explain anything again:
 * highlights are derived from score 0/1 + source_field/evidence data.
 */
export function AnnotatedSyllabus({ data }: Props) {
  const { technical } = useTechnicalView();
  const { data: syllabus, isLoading, isError } = useQuery({
    queryKey: ["syllabus", data.syllabus_seuid_snapshot],
    queryFn: () => getSyllabus(data.syllabus_seuid_snapshot),
    enabled: Boolean(data.syllabus_seuid_snapshot),
  });

  const judgmentByCriterion = useMemo(() => buildJudgmentIndex(data), [data]);
  const sections = useMemo(
    () => (syllabus ? buildSyllabusSections(syllabus) : []),
    [syllabus],
  );

  if (isLoading) {
    return (
      <EvaluationSection title="Syllabus annotato">
        <div className="h-40 animate-pulse bg-slate-100" />
      </EvaluationSection>
    );
  }

  if (isError || !syllabus) {
    return (
      <EvaluationSection title="Syllabus annotato">
        <p className="text-sm text-slate-600">
          Non è stato possibile caricare il syllabus originale per costruire
          la vista annotata.
        </p>
        <ReportFallback data={data} technical={technical} />
      </EvaluationSection>
    );
  }

  return (
    <EvaluationSection
      title="Syllabus annotato"
      aside={
        <span className="text-xs text-slate-500">
          Evidenziazioni: rosso = criticità · giallo = area migliorabile
        </span>
      }
    >
      <div className="space-y-8">
        <article className="mx-auto w-full max-w-[1120px] text-slate-900">
          <DocumentHeader syllabus={syllabus} />

          <div className="space-y-10">
            {sections.map((section) => (
              <AnnotatedSection
                key={section.id}
                section={section}
                annotations={annotationsForSection(
                  section,
                  data,
                  judgmentByCriterion,
                )}
              />
            ))}
          </div>
        </article>

        <ReportFallback data={data} technical={technical} />
      </div>
    </EvaluationSection>
  );
}

function DocumentHeader({ syllabus }: { syllabus: SyllabusDetail }) {
  return (
    <header className="mb-8 border-b border-slate-300 pb-5">
      <h2 className="text-4xl font-semibold leading-tight tracking-normal text-slate-950 md:text-5xl">
        {syllabus.course_name}
      </h2>
      {syllabus.module ? (
        <p className="mt-2 text-2xl font-semibold leading-tight text-slate-900 md:text-3xl">
          Modulo {syllabus.module}
        </p>
      ) : null}
      <p className="mt-5 text-sm text-slate-700">
        <strong>Anno accademico {syllabus.academic_year || "—"}</strong>
        {" - "}
        Docente:{" "}
        <span className="font-semibold uppercase text-sky-700">
          {syllabus.teacher || "—"}
        </span>
      </p>
    </header>
  );
}

function AnnotatedSection({
  section,
  annotations,
}: {
  section: SyllabusSection;
  annotations: SectionAnnotation[];
}) {
  const primaryTone = annotations.some((annotation) => annotation.score === 0)
    ? "critical"
    : annotations.length > 0
      ? "improvable"
      : null;

  return (
    <section
      id={`annotated-${section.id}`}
      className={
        "scroll-mt-24 " +
        (primaryTone === "critical"
          ? "border-l-4 border-rose-400 pl-4"
          : primaryTone === "improvable"
            ? "border-l-4 border-amber-300 pl-4"
            : "")
      }
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-3xl font-semibold leading-tight tracking-normal text-slate-950 md:text-4xl">
          {section.title}
        </h3>
        {annotations.length > 0 ? (
          <span
            className={
              "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium " +
              (primaryTone === "critical"
                ? "bg-rose-50 text-rose-700"
                : "bg-amber-50 text-amber-700")
            }
          >
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
            {primaryTone === "critical" ? "Criticità" : "Da migliorare"}
          </span>
        ) : null}
      </div>

      <SectionBody section={section} tone={primaryTone} />

      {annotations.length > 0 ? <AnnotationDetails annotations={annotations} /> : null}
    </section>
  );
}

function SectionBody({
  section,
  tone,
}: {
  section: SyllabusSection;
  tone: AnnotationTone | null;
}) {
  const highlight =
    tone === "critical"
      ? "decoration-rose-400/80 decoration-[0.18em] underline-offset-4"
      : tone === "improvable"
        ? "decoration-amber-300/90 decoration-[0.18em] underline-offset-4"
        : "";

  if (section.paragraphs) {
    return (
      <div className="space-y-8">
        {section.paragraphs.map((paragraph) => {
          const blocks = syllabusProseParagraphs(paragraph.text);
          return (
            <div key={paragraph.label} className="space-y-4">
              {(blocks.length > 0 ? blocks : ["—"]).map((block, index) => (
                <p
                  key={`${paragraph.label}-${index}`}
                  className={`text-[1.05rem] leading-8 text-slate-800 ${highlight ? `underline decoration-skip-ink ${highlight}` : ""}`}
                >
                  {index === 0 ? <><em>{paragraph.label}:</em>{" "}</> : null}
                  {block}
                </p>
              ))}
            </div>
          );
        })}
      </div>
    );
  }

  if (section.schedule) {
    return <ScheduleTable items={section.schedule} />;
  }

  const blocks = syllabusProseParagraphs(section.body);
  return (
    <div className="space-y-4">
      {(blocks.length > 0 ? blocks : ["—"]).map((block, index) => (
        <p
          key={index}
          className={`text-[1.05rem] leading-8 text-slate-800 ${highlight ? `underline decoration-skip-ink ${highlight}` : ""}`}
        >
          {block}
        </p>
      ))}
    </div>
  );
}

function AnnotationDetails({ annotations }: { annotations: SectionAnnotation[] }) {
  return (
    <div className="mt-4 space-y-2">
      {annotations.map((annotation) => (
        <details
          key={annotation.code}
          className={
            "group border-y px-3 py-2 " +
            (annotation.tone === "critical"
              ? "border-rose-200 bg-rose-50/70"
              : "border-amber-200 bg-amber-50/70")
          }
        >
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-slate-900">
            <MessageSquareText className="h-4 w-4 text-slate-500" aria-hidden />
            Perché è evidenziato?{" "}
            <code className="font-mono text-xs text-slate-500">
              {annotation.code}
            </code>
            <span className="text-slate-500">{annotation.name}</span>
          </summary>
          <div className="mt-3 space-y-2 text-sm leading-relaxed text-slate-700">
            {annotation.justification ? <p>{annotation.justification}</p> : null}
            {annotation.evidence ? (
              <blockquote className="border-l border-slate-300 pl-3 text-slate-600">
                “{annotation.evidence}”
              </blockquote>
            ) : null}
            <p className="flex items-center gap-1.5 text-xs text-slate-500">
              <Info className="h-3.5 w-3.5" aria-hidden />
              L’evidenziazione indica una sezione collegata al criterio, non
              necessariamente che tutto il testo sia errato.
            </p>
          </div>
        </details>
      ))}
    </div>
  );
}

function ScheduleTable({ items }: { items: SyllabusDetail["schedule_it"] }) {
  if (!items || items.length === 0) {
    return <p className="text-[1.05rem] leading-8 text-slate-700">—</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-300 text-slate-700">
          <tr>
            <th className="w-12 px-3 py-2 text-left font-semibold">N°</th>
            <th className="px-3 py-2 text-left font-semibold">Argomenti</th>
            <th className="w-48 px-3 py-2 text-left font-semibold">
              Riferimenti testi
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const topic =
              item.argomenti ??
              item.subjects ??
              item.subject ??
              item.topics ??
              item.topic ??
              "";
            const references =
              item.riferimenti_testi ??
              item.text_references ??
              item.textbook_references ??
              item.references ??
              "";
            return (
              <tr key={index} className="border-b border-slate-200">
                <td className="px-3 py-2 align-top tabular-nums text-slate-600">
                  {item.numero ?? index + 1}
                </td>
                <td className="px-3 py-2 align-top">{topic || "—"}</td>
                <td className="px-3 py-2 align-top text-slate-600">
                  {references || "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ReportFallback({
  data,
  technical,
}: {
  data: EvaluationDetail;
  technical: boolean;
}) {
  const redactRawReport = !technical && data.status === "failed";
  return (
    <details className="mx-auto w-full max-w-[1120px] border-t border-slate-200 pt-4">
      <summary className="cursor-pointer text-sm font-medium text-slate-700 hover:text-slate-950">
        Report testuale della valutazione
      </summary>
      <div className="mt-4">
        {redactRawReport ? (
          <p className="text-sm text-slate-600">
            Il report non è disponibile perché la valutazione non è stata
            completata. I dettagli di esecuzione sono disponibili agli account
            con ruolo tecnico o amministrativo.
          </p>
        ) : data.final_report ? (
          <ReportMarkdown source={data.final_report} />
        ) : (
          <p className="text-sm text-slate-500">
            Il report testuale sarà disponibile al termine della sintesi.
          </p>
        )}
      </div>
    </details>
  );
}

function buildSyllabusSections(syllabus: SyllabusDetail): SyllabusSection[] {
  return [
    {
      id: "outcomes",
      title: "Risultati di apprendimento attesi",
      fields: [
        "learning_outcomes_it",
        "dublin_knowledge_it",
        "dublin_applying_it",
        "dublin_judgement_it",
        "dublin_communication_it",
        "dublin_learning_it",
        "learning_outcomes_en",
        "dublin_knowledge_en",
        "dublin_applying_en",
        "dublin_judgement_en",
        "dublin_communication_en",
        "dublin_learning_en",
      ],
      paragraphs: [
        {
          label: "Conoscenza e capacità di comprensione (knowledge and understanding)",
          text: getField(syllabus, "dublin_knowledge_it") ||
            getField(syllabus, "learning_outcomes_it"),
        },
        {
          label: "Capacità di applicare conoscenza e comprensione (applying knowledge and understanding)",
          text: getField(syllabus, "dublin_applying_it"),
        },
        {
          label: "Autonomia di giudizio (making judgements)",
          text: getField(syllabus, "dublin_judgement_it"),
        },
        {
          label: "Abilità comunicative (communication skills)",
          text: getField(syllabus, "dublin_communication_it"),
        },
        {
          label: "Capacità di apprendimento (learning skills)",
          text: getField(syllabus, "dublin_learning_it"),
        },
      ].filter((paragraph) => paragraph.text),
    },
    {
      id: "teaching_methods",
      title: "Modalità di svolgimento dell'insegnamento",
      fields: ["teaching_methods_it", "teaching_methods_en"],
      body: getField(syllabus, "teaching_methods_it"),
    },
    {
      id: "prerequisites",
      title: "Prerequisiti richiesti",
      fields: ["prerequisites_it", "prerequisites_en"],
      body: getField(syllabus, "prerequisites_it"),
    },
    {
      id: "attendance",
      title: "Frequenza lezioni",
      fields: ["attendance_it", "attendance_en"],
      body: getField(syllabus, "attendance_it"),
    },
    {
      id: "content",
      title: "Contenuti del corso",
      fields: ["course_content_it", "course_content_en"],
      body: getField(syllabus, "course_content_it"),
    },
    {
      id: "references",
      title: "Testi di riferimento",
      fields: ["references_it", "references_en"],
      body: getField(syllabus, "references_it"),
    },
    {
      id: "schedule",
      title: "Programmazione del corso",
      fields: ["schedule_it", "schedule_en"],
      schedule: syllabus.schedule_it,
    },
    {
      id: "assessment",
      title: "Modalità di verifica dell'apprendimento",
      fields: ["assessment_methods_it", "assessment_methods_en"],
      body: getField(syllabus, "assessment_methods_it"),
    },
    {
      id: "sample_questions",
      title: "Esempi di domande e/o esercizi frequenti",
      fields: ["sample_questions_it", "sample_questions_en"],
      body: getField(syllabus, "sample_questions_it"),
    },
  ].filter((section) => section.paragraphs?.length || section.body || section.schedule);
}

function annotationsForSection(
  section: SyllabusSection,
  data: EvaluationDetail,
  judgmentByCriterion: Map<string, CriterionJudgmentDump>,
): SectionAnnotation[] {
  const scores = data.criterion_scores ?? {};
  const sectionCriteria = new Set(FALLBACK_SECTION_CRITERIA[section.id] ?? []);
  const out: SectionAnnotation[] = [];

  for (const criterion of CORE_CRITERIA) {
    const rawScore = scores[criterion.code];
    if (rawScore !== 0 && rawScore !== 1) continue;
    const judgment = judgmentByCriterion.get(criterion.code) ?? null;
    const evidenceFields = new Set(
      (judgment?.evidences ?? [])
        .map((evidence) => evidence.source_field)
        .filter(Boolean),
    );
    const hasDirectEvidence = section.fields.some((field) =>
      evidenceFields.has(field),
    );
    const hasFallback = sectionCriteria.has(criterion.code);
    if (!hasDirectEvidence && !hasFallback) continue;
    const evidence =
      (judgment?.evidences ?? []).find((item) =>
        section.fields.includes(item.source_field),
      )?.text ??
      judgment?.evidences?.[0]?.text ??
      null;
    out.push({
      code: criterion.code,
      name: criterionMeta.get(criterion.code)?.name ?? criterion.code,
      score: rawScore,
      tone: rawScore === 0 ? "critical" : "improvable",
      justification: judgment?.justification ?? null,
      evidence,
      sourceFields: Array.from(evidenceFields),
    });
  }

  return out.sort((a, b) => a.score - b.score || a.code.localeCompare(b.code));
}

function buildJudgmentIndex(
  data: EvaluationDetail,
): Map<string, CriterionJudgmentDump> {
  const out = new Map<string, CriterionJudgmentDump>();
  const outputs = data.agent_outputs ?? null;
  if (!outputs) return out;
  for (const agentOut of Object.values(outputs)) {
    if (!agentOut) continue;
    for (const judgment of agentOut.judgments) {
      out.set(judgment.criterion_code, judgment);
    }
  }
  return out;
}

function getField(syllabus: SyllabusDetail, field: keyof SyllabusDetail): string {
  const value = syllabus[field];
  return typeof value === "string" ? value : "";
}

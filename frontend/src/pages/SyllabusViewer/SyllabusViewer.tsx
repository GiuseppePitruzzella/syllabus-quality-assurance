import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ExternalLink, Loader2, Sparkles } from "lucide-react";
import {
  getSyllabus,
  listEvaluationsForSyllabus,
} from "@/lib/api";
import type { EvaluationSummary, SyllabusDetail } from "@/lib/types";
import { useAutoScrape } from "@/hooks/useAutoScrape";
import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { cleanSyllabusDisplayText } from "@/lib/text";
import { LanguageToggle } from "@/components/LanguageToggle";
import { StatusBadge } from "@/components/StatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { Section } from "@/components/layout/Section";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { DublinDescriptors } from "./DublinDescriptors";
import { CourseScheduleTable } from "./CourseScheduleTable";
import { EvaluatePreflightDialog } from "./EvaluatePreflightDialog";
import { MetadataSidebar } from "./MetadataSidebar";

/**
 * Phase 9.E.2 — the Evaluate button always opens the preflight
 * dialog. Direct submission was retired so a user can never start
 * a run without first seeing the informational perimeter (which
 * documents will feed E1-E5).
 */
function EvaluateButton({
  seuid,
  courseName,
}: {
  seuid: string;
  courseName: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        size="lg"
        onClick={() => setOpen(true)}
        className="rounded-none bg-slate-950 text-white shadow-none hover:bg-slate-800 hover:shadow-none"
      >
        <Sparkles className="h-4 w-4" aria-hidden />
        Valuta
      </Button>
      <EvaluatePreflightDialog
        open={open}
        onOpenChange={setOpen}
        seuid={seuid}
        courseName={courseName}
      />
    </>
  );
}


function SourceLink({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex h-9 items-center gap-1.5 bg-slate-100 px-3 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200 hover:text-slate-950"
    >
      {label}
      <ExternalLink className="h-3 w-3" aria-hidden />
    </a>
  );
}

export function SyllabusViewer() {
  const { seuid } = useParams<{ seuid: string }>();
  const [lang, setLang] = useState<"it" | "en">("it");

  const { data, isLoading } = useQuery({
    queryKey: ["syllabus", seuid],
    queryFn: () => getSyllabus(seuid!),
    enabled: !!seuid,
  });

  const { data: evaluationHistory = [], isLoading: isHistoryLoading } =
    useQuery({
      queryKey: ["evaluations", "syllabus", seuid],
      queryFn: () => listEvaluationsForSyllabus(seuid!, 10),
      enabled: !!seuid,
    });

  const autoScrape = useAutoScrape(data);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-[1720px] py-10">
        <p className="text-sm text-muted-foreground">Caricamento…</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-[1720px] py-10">
        <p className="text-sm text-muted-foreground">Syllabus non trovato.</p>
      </div>
    );
  }

  if (autoScrape.isLoading) {
    return (
      <div className="mx-auto flex max-w-[1720px] flex-col items-center justify-center gap-3 py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Scaricamento contenuto in corso…
        </p>
      </div>
    );
  }

  const textField = (field: string): string => {
    const key = `${field}_${lang}` as keyof SyllabusDetail;
    return cleanSyllabusDisplayText((data[key] as string) || "");
  };

  const breadcrumbItems = [
    {
      label: data.department_name ?? "Dipartimento",
      to: `/?dept=${data.department_id}`,
    },
    {
      label: data.cdl_name ?? "CdL",
      to: `/?dept=${data.department_id}&cdl=${data.cdl_id}`,
    },
    { label: data.course_name },
  ];
  const subtitleParts = [
    data.teacher,
    data.cdl_name ?? "CdL",
    data.academic_year,
  ].filter(Boolean);

  return (
    <div className="mx-auto w-full max-w-[1720px] space-y-10">
      <Breadcrumb items={breadcrumbItems} />

      <PageHeader
        badge="Syllabus"
        title={data.course_name}
        subtitle={subtitleParts.join(" · ")}
        pills={
          <>
            <LanguagePill hasEnglish={data.has_english} />
            {data.year_of_study ? (
              <Pill tone="neutral">Anno {data.year_of_study}</Pill>
            ) : null}
            {data.module ? <Pill tone="neutral">{data.module}</Pill> : null}
            {data.course_code ? (
              <Pill tone="muted">Cod. {data.course_code}</Pill>
            ) : null}
          </>
        }
        actions={
          <>
            <SourceLink href={data.url_it} label="Fonte IT" />
            {data.has_english ? (
              <SourceLink href={data.url_en} label="Fonte EN" />
            ) : null}
            <LanguageToggle
              value={lang}
              onChange={setLang}
              hasEnglish={data.has_english}
            />
            <EvaluateButton
              seuid={data.seuid}
              courseName={data.course_name ?? data.seuid}
            />
          </>
        }
      />

      {/* Metadata strip (full-width, dense) */}
      <MetadataSidebar data={data} />

      {/* Valutazioni precedenti */}
      <EvaluationHistoryList
        items={evaluationHistory}
        isLoading={isHistoryLoading}
      />

        <Section
        title="Contenuto syllabus"
        headerAside={
          <span className="text-xs text-muted-foreground">
            Lingua attiva:{" "}
            <strong className="font-medium text-foreground">
              {lang.toUpperCase()}
            </strong>
          </span>
        }
      >
          <Tabs defaultValue="obiettivi">
            <TabsList
              variant="line"
              className="w-full justify-start overflow-x-auto p-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              <TabsTrigger value="obiettivi">Obiettivi formativi</TabsTrigger>
              <TabsTrigger value="contenuto">
                Contenuto e programma
              </TabsTrigger>
              <TabsTrigger value="metodologia">Metodologia</TabsTrigger>
              <TabsTrigger value="verifica">Verifica</TabsTrigger>
              <TabsTrigger value="risorse">Risorse</TabsTrigger>
            </TabsList>

            <TabsContent value="obiettivi" className="mt-4">
              <DublinDescriptors data={data} lang={lang} />
            </TabsContent>

            <TabsContent value="contenuto" className="mt-4 space-y-5">
              <SectionField
                label="Contenuto del corso"
                text={textField("course_content")}
              />
              <div>
                <SectionLabel>Programmazione</SectionLabel>
                <CourseScheduleTable
                  items={lang === "it" ? data.schedule_it : data.schedule_en}
                />
              </div>
            </TabsContent>

            <TabsContent value="metodologia" className="mt-4 space-y-5">
              <SectionField
                label="Metodi di insegnamento"
                text={textField("teaching_methods")}
              />
              <SectionField
                label="Frequenza"
                text={textField("attendance")}
              />
              <SectionField
                label="Prerequisiti"
                text={textField("prerequisites")}
              />
            </TabsContent>

            <TabsContent value="verifica" className="mt-4 space-y-5">
              <SectionField
                label="Metodi di valutazione"
                text={textField("assessment_methods")}
              />
              <SectionField
                label="Domande di esempio"
                text={textField("sample_questions")}
              />
            </TabsContent>

            <TabsContent value="risorse" className="mt-4">
              <SectionField
                label="Riferimenti"
                text={textField("references")}
              />
            </TabsContent>
          </Tabs>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function LanguagePill({ hasEnglish }: { hasEnglish: boolean }) {
  if (hasEnglish) {
    return (
      <span className="inline-flex items-center bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-800">
        IT + EN
      </span>
    );
  }
  return (
    <span className="inline-flex items-center bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-800">
      Solo IT
    </span>
  );
}

function Pill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "neutral" | "muted";
}) {
  const cls =
    tone === "neutral"
      ? "bg-slate-100 text-slate-800"
      : "bg-muted text-muted-foreground";
  return (
    <span
      className={
        "inline-flex items-center px-2 py-0.5 text-xs font-medium " +
        cls
      }
    >
      {children}
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="!m-0 mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {children}
    </h3>
  );
}

function SectionField({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <SectionLabel>{label}</SectionLabel>
      <p className="whitespace-pre-line text-sm leading-relaxed text-foreground/90">
        {text || "—"}
      </p>
    </div>
  );
}

function EvaluationHistoryList({
  items,
  isLoading,
}: {
  items: EvaluationSummary[];
  isLoading: boolean;
}) {
  return (
    <Section
      title="Valutazioni precedenti"
      description="Storico delle run salvate per questo syllabus."
      headerAside={
        isLoading ? (
          <span className="text-xs text-muted-foreground">caricamento…</span>
        ) : (
          <span className="bg-muted px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
            {items.length} run
          </span>
        )
      }
    >
      {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="h-11 animate-pulse rounded-md bg-muted"
                aria-hidden
              />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
            Nessuna valutazione registrata. Avvia una run con{" "}
            <strong className="font-medium text-foreground">
              Valuta
            </strong>
            .
          </p>
        ) : (
          <ul className="divide-y divide-slate-200/80">
            {items.map((item) => (
              <li key={item.evaluation_uuid}>
                <Link
                  to={`/evaluation/${item.evaluation_uuid}`}
                  className="grid gap-2 px-3 py-2.5 text-sm transition-colors hover:bg-muted/50 sm:grid-cols-[minmax(0,1fr)_auto_auto]"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={item.status} />
                      <code className="font-mono text-xs text-muted-foreground">
                        {item.evaluation_uuid.slice(0, 8)}
                      </code>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {formatDateTime(item.started_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground sm:justify-end">
                    <span>
                      CoreScore{" "}
                      <strong className="font-medium text-foreground tabular-nums">
                        {typeof item.core_score === "number"
                          ? item.core_score.toFixed(2)
                          : "—"}
                      </strong>
                    </span>
                    <span>
                      Coverage{" "}
                      <strong className="font-medium text-foreground tabular-nums">
                        {typeof item.coverage === "number"
                          ? `${Math.round(item.coverage * 100)}%`
                          : "—"}
                      </strong>
                    </span>
                  </div>
                  <span className="flex items-center gap-1 text-xs font-medium text-primary sm:justify-end">
                    Apri valutazione
                    <ArrowUpRight className="h-3 w-3" aria-hidden />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
    </Section>
  );
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

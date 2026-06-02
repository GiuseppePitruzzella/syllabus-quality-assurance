import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ExternalLink, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import {
  getSyllabus,
  listEvaluationsForSyllabus,
  startEvaluation,
} from "@/lib/api";
import type {
  EvaluationStatus,
  EvaluationSummary,
  SyllabusDetail,
} from "@/lib/types";
import { useAutoScrape } from "@/hooks/useAutoScrape";
import { Breadcrumb } from "@/components/Breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { DublinDescriptors } from "./DublinDescriptors";
import { CourseScheduleTable } from "./CourseScheduleTable";
import { MetadataSidebar } from "./MetadataSidebar";

function EvaluateButton({ seuid }: { seuid: string }) {
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: () => startEvaluation(seuid),
    onSuccess: (data) => {
      navigate(`/evaluation/${data.evaluation_uuid}`);
    },
    onError: (err) => {
      toast.error("Avvio valutazione fallito", {
        description: err instanceof Error ? err.message : String(err),
      });
    },
  });

  return (
    <Button
      size="sm"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      aria-busy={mutation.isPending}
    >
      {mutation.isPending ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <Sparkles className="h-4 w-4" aria-hidden />
      )}
      {mutation.isPending ? "Avvio…" : "Valuta syllabus"}
    </Button>
  );
}

function LangToggle({
  lang,
  setLang,
  hasEnglish,
}: {
  lang: "it" | "en";
  setLang: (l: "it" | "en") => void;
  hasEnglish: boolean;
}) {
  return (
    <div className="flex h-9 items-center rounded-md border bg-card p-0.5">
      <button
        type="button"
        onClick={() => setLang("it")}
        className={
          "rounded-sm px-3 py-1 text-xs font-medium transition-colors " +
          (lang === "it"
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground")
        }
      >
        IT
      </button>
      {hasEnglish ? (
        <button
          type="button"
          onClick={() => setLang("en")}
          className={
            "rounded-sm px-3 py-1 text-xs font-medium transition-colors " +
            (lang === "en"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground")
          }
        >
          EN
        </button>
      ) : (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger
              render={
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded-sm px-3 py-1 text-xs font-medium text-muted-foreground/40"
                >
                  EN
                </button>
              }
            />
            <TooltipContent>Versione inglese non disponibile</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
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
      className="inline-flex h-9 items-center gap-1.5 rounded-md border bg-card px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
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
      <div className="mx-auto max-w-6xl py-10">
        <p className="text-sm text-muted-foreground">Caricamento…</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-6xl py-10">
        <p className="text-sm text-muted-foreground">Syllabus non trovato.</p>
      </div>
    );
  }

  if (autoScrape.isLoading) {
    return (
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-center gap-3 py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Scaricamento contenuto in corso…
        </p>
      </div>
    );
  }

  const textField = (field: string): string => {
    const key = `${field}_${lang}` as keyof SyllabusDetail;
    return (data[key] as string) || "";
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

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Breadcrumb items={breadcrumbItems} />

      {/* Header SaaS */}
      <header className="flex flex-wrap items-end justify-between gap-4 border-b pb-5">
        <div className="min-w-0">
          <Badge
            variant="outline"
            className="mb-3 border-cyan-200 bg-cyan-500/10 text-cyan-800"
          >
            Syllabus
          </Badge>
          <h1 className="!my-0 !text-3xl !font-semibold !tracking-normal md:!text-4xl">
            {data.course_name}
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {data.teacher} · {data.cdl_name ?? "CdL"} ·{" "}
            {data.academic_year}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <LanguagePill hasEnglish={data.has_english} />
            {data.year_of_study ? (
              <Pill tone="neutral">Anno {data.year_of_study}</Pill>
            ) : null}
            {data.module ? <Pill tone="neutral">{data.module}</Pill> : null}
            {data.course_code ? (
              <Pill tone="muted">Cod. {data.course_code}</Pill>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SourceLink href={data.url_it} label="Fonte IT" />
          {data.has_english ? (
            <SourceLink href={data.url_en} label="Fonte EN" />
          ) : null}
          <LangToggle
            lang={lang}
            setLang={setLang}
            hasEnglish={data.has_english}
          />
          <EvaluateButton seuid={data.seuid} />
        </div>
      </header>

      {/* Metadata strip (full-width, dense) */}
      <MetadataSidebar data={data} />

      {/* Valutazioni precedenti */}
      <EvaluationHistoryList
        items={evaluationHistory}
        isLoading={isHistoryLoading}
      />

      {/* Contenuto syllabus */}
      <section className="rounded-lg border bg-card">
        <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
          <h2 className="!m-0 !text-base !font-semibold !tracking-normal">
            Contenuto syllabus
          </h2>
          <span className="text-xs text-muted-foreground">
            Lingua attiva:{" "}
            <strong className="font-medium text-foreground">
              {lang.toUpperCase()}
            </strong>
          </span>
        </div>
        <div className="p-4">
          <Tabs defaultValue="obiettivi">
            <TabsList>
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
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function LanguagePill({ hasEnglish }: { hasEnglish: boolean }) {
  if (hasEnglish) {
    return (
      <span className="inline-flex items-center rounded-md border border-emerald-200 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-800">
        IT + EN
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-md border border-amber-200 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-800">
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
      ? "border-border bg-card text-foreground"
      : "border-transparent bg-muted text-muted-foreground";
  return (
    <span
      className={
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium " +
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
    <section className="rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h2 className="!m-0 !text-base !font-semibold !tracking-normal">
            Valutazioni precedenti
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Storico delle run salvate per questo syllabus.
          </p>
        </div>
        {isLoading ? (
          <span className="text-xs text-muted-foreground">caricamento…</span>
        ) : (
          <span className="rounded-md border bg-muted px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
            {items.length} run
          </span>
        )}
      </div>

      <div className="p-4">
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
          <p className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
            Nessuna valutazione registrata. Avvia una run con{" "}
            <strong className="font-medium text-foreground">
              Valuta syllabus
            </strong>
            .
          </p>
        ) : (
          <ul className="divide-y rounded-md border">
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
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: EvaluationStatus }) {
  const config: Record<
    EvaluationStatus,
    {
      label: string;
      className?: string;
      variant: "default" | "secondary" | "destructive" | "outline";
    }
  > = {
    pending: { label: "in attesa", variant: "secondary" },
    running: { label: "in esecuzione", variant: "default" },
    completed: {
      label: "completata",
      variant: "outline",
      className:
        "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    },
    partial: {
      label: "parziale",
      variant: "outline",
      className:
        "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    },
    failed: { label: "fallita", variant: "destructive" },
  };
  const entry = config[status];
  return (
    <Badge variant={entry.variant} className={entry.className}>
      {entry.label}
    </Badge>
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

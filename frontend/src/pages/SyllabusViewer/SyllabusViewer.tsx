import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Loader2, Sparkles } from "lucide-react";
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
    <div className="flex gap-1">
      <Button
        size="sm"
        variant={lang === "it" ? "default" : "ghost"}
        onClick={() => setLang("it")}
      >
        IT
      </Button>
      {hasEnglish ? (
        <Button
          size="sm"
          variant={lang === "en" ? "default" : "ghost"}
          onClick={() => setLang("en")}
        >
          EN
        </Button>
      ) : (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger
              render={
                <Button size="sm" variant="ghost" disabled>
                  EN
                </Button>
              }
            />
            <TooltipContent>
              Versione inglese non disponibile
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
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
    return <p className="text-muted-foreground">Caricamento...</p>;
  }

  if (!data) {
    return <p className="text-muted-foreground">Syllabus non trovato.</p>;
  }

  if (autoScrape.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">
          Scaricamento contenuto in corso...
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
    <div>
      <Breadcrumb items={breadcrumbItems} />

      <div className="flex items-center justify-between mb-6 gap-3">
        <h1 className="text-2xl font-bold">{data.course_name}</h1>
        <div className="flex items-center gap-3">
          <EvaluateButton seuid={data.seuid} />
          <LangToggle
            lang={lang}
            setLang={setLang}
            hasEnglish={data.has_english}
          />
        </div>
      </div>

      <EvaluationHistoryList
        items={evaluationHistory}
        isLoading={isHistoryLoading}
      />

      <div className="flex gap-6">
        <div className="flex-1 min-w-0">
          <Tabs defaultValue="obiettivi">
            <TabsList>
              <TabsTrigger value="obiettivi">Obiettivi Formativi</TabsTrigger>
              <TabsTrigger value="contenuto">
                Contenuto e Programma
              </TabsTrigger>
              <TabsTrigger value="metodologia">Metodologia</TabsTrigger>
              <TabsTrigger value="verifica">Verifica</TabsTrigger>
              <TabsTrigger value="risorse">Risorse</TabsTrigger>
            </TabsList>

            <TabsContent value="obiettivi" className="mt-4">
              <DublinDescriptors data={data} lang={lang} />
            </TabsContent>

            <TabsContent value="contenuto" className="mt-4 space-y-6">
              <div>
                <h3 className="font-semibold mb-2">Contenuto del corso</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("course_content") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Programmazione</h3>
                <CourseScheduleTable
                  items={
                    lang === "it" ? data.schedule_it : data.schedule_en
                  }
                />
              </div>
            </TabsContent>

            <TabsContent value="metodologia" className="mt-4 space-y-6">
              <div>
                <h3 className="font-semibold mb-2">Metodi di insegnamento</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("teaching_methods") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Frequenza</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("attendance") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Prerequisiti</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("prerequisites") || "\u2014"}
                </p>
              </div>
            </TabsContent>

            <TabsContent value="verifica" className="mt-4 space-y-6">
              <div>
                <h3 className="font-semibold mb-2">Metodi di valutazione</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("assessment_methods") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Domande di esempio</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("sample_questions") || "\u2014"}
                </p>
              </div>
            </TabsContent>

            <TabsContent value="risorse" className="mt-4">
              <div>
                <h3 className="font-semibold mb-2">Riferimenti</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("references") || "\u2014"}
                </p>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <MetadataSidebar data={data} />
      </div>
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
    <section className="mb-6 rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">Valutazioni precedenti</h2>
          <p className="text-xs text-muted-foreground">
            Storico delle run salvate per questo syllabus.
          </p>
        </div>
        {isLoading ? (
          <span className="text-xs text-muted-foreground">caricamento…</span>
        ) : (
          <span className="text-xs text-muted-foreground">
            {items.length} run
          </span>
        )}
      </div>

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
        <p className="rounded-md border border-dashed px-3 py-3 text-sm text-muted-foreground">
          Nessuna valutazione registrata. Avvia una run con il bottone
          “Valuta syllabus”.
        </p>
      ) : (
        <ul className="divide-y rounded-md border">
          {items.map((item) => (
            <li key={item.evaluation_uuid}>
              <Link
                to={`/evaluation/${item.evaluation_uuid}`}
                className="grid gap-2 px-3 py-2 text-sm transition-colors hover:bg-muted/50 sm:grid-cols-[minmax(0,1fr)_auto_auto]"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={item.status} />
                    <code className="font-mono text-xs text-muted-foreground">
                      {item.evaluation_uuid.slice(0, 8)}
                    </code>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {formatDateTime(item.started_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground sm:justify-end">
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
                <span className="flex items-center gap-1 text-xs text-primary sm:justify-end">
                  Apri
                  <ArrowUpRight className="h-3 w-3" aria-hidden />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
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

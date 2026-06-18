import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  CircleDashed,
  ClipboardCheck,
  FileText,
  MinusCircle,
  TrendingUp,
} from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Section } from "@/components/layout/Section";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CORE_CRITERIA } from "@/data/rubric";
import { getResultsSummary } from "@/lib/api";
import type {
  CriterionDistribution,
  EvaluationStatus,
  ResultsEvaluationRow,
  ResultsSummary,
} from "@/lib/types";

const criterionMeta = new Map(CORE_CRITERIA.map((item) => [item.code, item]));

export function ResultsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["results-summary"],
    queryFn: getResultsSummary,
  });

  if (isLoading) {
    return <ResultsSkeleton />;
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-[1600px] space-y-8">
        <PageHeader
          badge="Risultati"
          badgeTone="rose"
          title="Sintesi dei risultati"
          subtitle="Non è stato possibile caricare la sintesi delle valutazioni."
        />
        <div className="border-y border-rose-200 bg-rose-50 px-4 py-5 text-sm text-rose-700">
          Errore durante il caricamento dei risultati.
        </div>
      </div>
    );
  }

  const hasEvaluations = data.overview.latest_evaluations_count > 0;

  return (
    <div className="mx-auto max-w-[1600px] space-y-8">
      <PageHeader
        badge="Risultati"
        badgeTone="cyan"
        title="Sintesi dei risultati"
        subtitle="Una vista trasversale sulle ultime valutazioni disponibili per syllabus: qualità media, criteri più critici e stato della validazione umana."
        pills={
          <span className="text-xs text-slate-500">
            Ultimo aggiornamento: {formatDateTime(data.generated_at)}
          </span>
        }
      />

      {!hasEvaluations ? (
        <EmptyResults />
      ) : (
        <>
          <Overview data={data} />
          <CriteriaDistribution criteria={data.criteria} />
          <EvaluationsTable rows={data.evaluations} />
          <HumanValidation data={data} />
        </>
      )}
    </div>
  );
}

function Overview({ data }: { data: ResultsSummary }) {
  const { overview } = data;
  const scoredCount = overview.completed_count + overview.partial_count;

  return (
    <section aria-label="Panoramica risultati">
      <div className="grid gap-px overflow-hidden border-y border-slate-200 bg-slate-200 md:grid-cols-2 xl:grid-cols-4">
        <Kpi
          icon={<FileText className="h-4 w-4" />}
          label="Syllabus valutati"
          value={overview.latest_evaluations_count}
          hint={`${overview.terminal_runs_count} run terminali registrate`}
        />
        <Kpi
          icon={<TrendingUp className="h-4 w-4" />}
          label="CoreScore medio"
          value={formatScore(overview.average_core_score)}
          hint={`${scoredCount} valutazioni con punteggio`}
        />
        <Kpi
          icon={<ClipboardCheck className="h-4 w-4" />}
          label="Copertura media"
          value={formatPercent(overview.average_coverage)}
          hint="Criteri C1-C9 valutabili"
        />
        <Kpi
          icon={<AlertTriangle className="h-4 w-4" />}
          label="Aree da presidiare"
          value={overview.total_critical_criteria + overview.total_improvable_criteria}
          hint={`${overview.total_critical_criteria} criticità · ${overview.total_improvable_criteria} aree da migliorare`}
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <StatusPill status="completed" count={overview.completed_count} />
        <StatusPill status="partial" count={overview.partial_count} />
        <StatusPill status="failed" count={overview.failed_count} />
        {overview.total_na_criteria > 0 ? (
          <span className="inline-flex items-center gap-1 bg-slate-100 px-2.5 py-1 text-slate-600">
            <MinusCircle className="h-3.5 w-3.5" />
            {overview.total_na_criteria} criteri non valutabili
          </span>
        ) : null}
      </div>
    </section>
  );
}

function CriteriaDistribution({
  criteria,
}: {
  criteria: CriterionDistribution[];
}) {
  const sorted = useMemo(
    () =>
      [...criteria].sort(
        (a, b) =>
          b.score_0 - a.score_0 ||
          b.score_1 - a.score_1 ||
          a.criterion_code.localeCompare(b.criterion_code),
      ),
    [criteria],
  );
  const topIssue = sorted.find((item) => item.score_0 + item.score_1 > 0);

  return (
    <Section
      title="Distribuzione C1-C9"
      description="Conteggio dei punteggi per criterio sulle ultime valutazioni terminali con punteggi disponibili. Le run fallite sono escluse dalla distribuzione."
      headerAside={
        topIssue ? (
          <span className="text-xs text-slate-500">
            Più ricorrente:{" "}
            <strong className="font-medium text-slate-800">
              {topIssue.criterion_code}{" "}
              {criterionMeta.get(topIssue.criterion_code)?.name}
            </strong>
          </span>
        ) : null
      }
    >
      <div className="divide-y divide-slate-200 border-y border-slate-200">
        {CORE_CRITERIA.map((criterion) => {
          const row = criteria.find((item) => item.criterion_code === criterion.code);
          if (!row) return null;
          return <CriterionRow key={criterion.code} row={row} />;
        })}
      </div>
    </Section>
  );
}

function CriterionRow({ row }: { row: CriterionDistribution }) {
  const meta = criterionMeta.get(row.criterion_code);
  const total = row.score_0 + row.score_1 + row.score_2 + row.na;

  return (
    <div className="grid gap-4 py-4 md:grid-cols-[minmax(220px,0.7fr)_1fr]">
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-xs font-semibold text-slate-500">
            {row.criterion_code}
          </span>
          <h3 className="truncate text-sm font-semibold text-slate-950">
            {meta?.name ?? row.criterion_code}
          </h3>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">
          {meta?.area ?? "Criterio core"}
        </p>
      </div>

      <div className="space-y-2">
        <StackedBar row={row} total={total} />
        <div className="flex flex-wrap gap-2 text-[11px] text-slate-600">
          <LegendDot tone="rose" label={`0 criticità: ${row.score_0}`} />
          <LegendDot tone="amber" label={`1 migliorabile: ${row.score_1}`} />
          <LegendDot tone="emerald" label={`2 adeguato: ${row.score_2}`} />
          {row.na > 0 ? <LegendDot tone="slate" label={`NA: ${row.na}`} /> : null}
        </div>
      </div>
    </div>
  );
}

function EvaluationsTable({ rows }: { rows: ResultsEvaluationRow[] }) {
  return (
    <Section
      title="Ultime valutazioni"
      description="Una riga per syllabus, usando l’ultima valutazione terminale disponibile. Apri il dettaglio per leggere motivazioni, evidenze e report."
      padded={false}
    >
      <Table className="w-full table-fixed">
        <TableHeader>
          <TableRow className="bg-transparent hover:bg-transparent">
            <TableHead>Insegnamento</TableHead>
            <TableHead className="w-32">Stato</TableHead>
            <TableHead className="w-28 text-right">CoreScore</TableHead>
            <TableHead className="w-28 text-right">Criticità</TableHead>
            <TableHead className="w-36 text-right">Da migliorare</TableHead>
            <TableHead className="w-24 text-right">Azione</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.evaluation_uuid} className="hover:bg-slate-100/60">
              <TableCell className="min-w-0">
                <div className="truncate font-medium text-slate-950">
                  {row.course_name}
                </div>
                <div className="mt-0.5 truncate text-xs text-slate-500">
                  {row.cdl_code ? `${row.cdl_code} · ` : ""}
                  {row.cdl_name ?? "CdL non disponibile"}
                </div>
              </TableCell>
              <TableCell>
                <StatusPill status={row.status} count={null} />
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {formatScore(row.core_score)}
              </TableCell>
              <TableCell className="text-right text-sm tabular-nums text-rose-700">
                {row.critical_count}
              </TableCell>
              <TableCell className="text-right text-sm tabular-nums text-amber-700">
                {row.improvable_count}
              </TableCell>
              <TableCell className="text-right">
                <Link
                  to={`/evaluation/${row.evaluation_uuid}`}
                  className="inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-slate-600 transition-colors hover:text-sky-700"
                >
                  Apri
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Section>
  );
}

function HumanValidation({ data }: { data: ResultsSummary }) {
  return (
    <Section title="Validazione umana" description="Fase 5.8">
      <div className="border-y border-slate-200 py-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-950">
              {data.human_validation.title}
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
              {data.human_validation.description}
            </p>
          </div>
          <span className="inline-flex w-fit items-center gap-2 bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600">
            <CircleDashed className="h-3.5 w-3.5" />
            In preparazione
          </span>
        </div>
      </div>
    </Section>
  );
}

function Kpi({
  icon,
  label,
  value,
  hint,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  hint: string;
}) {
  return (
    <div className="bg-white px-4 py-4">
      <div className="flex items-center gap-2 text-slate-500">
        {icon}
        <p className="text-[10px] font-semibold uppercase tracking-wide">
          {label}
        </p>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-normal text-slate-950">
        {value}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">{hint}</p>
    </div>
  );
}

function StackedBar({ row, total }: { row: CriterionDistribution; total: number }) {
  if (total === 0) {
    return <div className="h-2 bg-slate-100" />;
  }
  const segments = [
    { value: row.score_0, className: "bg-rose-500" },
    { value: row.score_1, className: "bg-amber-400" },
    { value: row.score_2, className: "bg-emerald-500" },
    { value: row.na, className: "bg-slate-300" },
  ];
  return (
    <div className="flex h-2 overflow-hidden bg-slate-100" aria-hidden>
      {segments.map((segment, index) =>
        segment.value > 0 ? (
          <div
            key={index}
            className={segment.className}
            style={{ width: `${(segment.value / total) * 100}%` }}
          />
        ) : null,
      )}
    </div>
  );
}

function LegendDot({
  tone,
  label,
}: {
  tone: "rose" | "amber" | "emerald" | "slate";
  label: string;
}) {
  const cls = {
    rose: "bg-rose-500",
    amber: "bg-amber-400",
    emerald: "bg-emerald-500",
    slate: "bg-slate-300",
  }[tone];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2 w-2 ${cls}`} aria-hidden />
      {label}
    </span>
  );
}

function StatusPill({
  status,
  count,
}: {
  status: EvaluationStatus;
  count: number | null;
}) {
  const meta = {
    completed: {
      label: "Completate",
      singular: "Completata",
      className: "bg-emerald-50 text-emerald-700",
      icon: CheckCircle2,
    },
    partial: {
      label: "Parziali",
      singular: "Parziale",
      className: "bg-amber-50 text-amber-700",
      icon: CircleDashed,
    },
    failed: {
      label: "Fallite",
      singular: "Fallita",
      className: "bg-rose-50 text-rose-700",
      icon: AlertTriangle,
    },
    pending: {
      label: "In attesa",
      singular: "In attesa",
      className: "bg-slate-100 text-slate-600",
      icon: CircleDashed,
    },
    running: {
      label: "In corso",
      singular: "In corso",
      className: "bg-sky-50 text-sky-700",
      icon: CircleDashed,
    },
  }[status];
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium ${meta.className}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {count === null ? meta.singular : `${count} ${meta.label.toLowerCase()}`}
    </span>
  );
}

function EmptyResults() {
  return (
    <div className="border-y border-slate-200 py-16">
      <div className="mx-auto max-w-2xl text-center">
        <BarChart3 className="mx-auto h-8 w-8 text-slate-400" />
        <h2 className="mt-4 text-xl font-semibold text-slate-950">
          Nessuna valutazione conclusa
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-600">
          La pagina Risultati si popolerà quando almeno un syllabus avrà una
          valutazione terminale. Parti dalla Dashboard, scegli un syllabus e
          avvia una valutazione.
        </p>
        <Link
          to="/"
          className="mt-5 inline-flex items-center justify-center bg-sky-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-sky-700"
        >
          Vai alla Dashboard
        </Link>
      </div>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="mx-auto max-w-[1600px] space-y-8">
      <PageHeader
        badge="Risultati"
        title="Sintesi dei risultati"
        subtitle="Caricamento della sintesi sperimentale."
      />
      <div className="grid gap-px overflow-hidden border-y border-slate-200 bg-slate-200 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="bg-white px-4 py-4">
            <div className="h-3 w-28 animate-pulse bg-slate-200" />
            <div className="mt-4 h-8 w-16 animate-pulse bg-slate-200" />
            <div className="mt-3 h-3 w-40 animate-pulse bg-slate-100" />
          </div>
        ))}
      </div>
    </div>
  );
}

function formatScore(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

function formatPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

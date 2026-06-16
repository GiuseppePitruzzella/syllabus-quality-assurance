import { useEffect, useRef, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  BookOpen,
  Building2,
  GraduationCap,
  Languages,
} from "lucide-react";

import { Section } from "@/components/layout/Section";
import { getStats } from "@/lib/api";

import { CdlSelector } from "./CdlSelector";
import { DepartmentSelector } from "./DepartmentSelector";
import { SyllabiTable } from "./SyllabiTable";

/**
 * Phase 10.A R2 — dashboard aligned with the EvaluationPage grammar:
 * full-width shell, editorial header, KPI strip as a neutral data row,
 * and content sections separated by spacing rather than cards.
 */
export function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const syllabiRef = useRef<HTMLDivElement>(null);

  const departmentId = parseUrlId(searchParams.get("dept"));
  const cdlId = departmentId
    ? parseUrlId(searchParams.get("cdl"))
    : null;

  function updateDashboardParams(
    nextDepartmentId: number | null,
    nextCdlId: number | null,
  ) {
    const next = new URLSearchParams(searchParams);
    if (nextDepartmentId === null) {
      next.delete("dept");
      next.delete("cdl");
    } else {
      next.set("dept", String(nextDepartmentId));
      if (nextCdlId === null) {
        next.delete("cdl");
      } else {
        next.set("cdl", String(nextCdlId));
      }
    }
    setSearchParams(next, { replace: true });
  }

  function handleDepartmentChange(id: number | null) {
    updateDashboardParams(id, null);
  }

  function handleCdlChange(id: number | null) {
    updateDashboardParams(departmentId, id);
  }

  // Phase 6.1.E — when the user lands on a CdL, scroll the syllabi
  // section to the top of the viewport. `window.scrollTo` (instead
  // of `scrollIntoView`) with an explicit offset is more reliable
  // when the target is already partially in view: scrollIntoView
  // can no-op or land short in that case. Two rAFs let React flush
  // the state update + layout before we measure.
  useEffect(() => {
    if (cdlId === null) return;
    const rafA = window.requestAnimationFrame(() => {
      const rafB = window.requestAnimationFrame(() => {
        const el = syllabiRef.current;
        if (!el) return;
        const top =
          window.scrollY + el.getBoundingClientRect().top - 16;
        window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
      });
      // safe cleanup if Dashboard unmounts between the two rAFs
      return () => window.cancelAnimationFrame(rafB);
    });
    return () => window.cancelAnimationFrame(rafA);
  }, [cdlId]);

  return (
    <div className="mx-auto w-full max-w-[1720px] space-y-10">
      <header className="space-y-7 pb-2">
        <div className="max-w-5xl">
          <p className="max-w-5xl text-[11px] font-medium uppercase leading-relaxed tracking-[0.08em] text-slate-500">
            Tesi di Laurea Magistrale di Giuseppe Pitruzzella | LM-18, UNICT |
            A.A. 2025/2026
          </p>
          <h1 className="mt-3 text-3xl font-semibold leading-tight text-slate-950 md:text-5xl">
            Syllabus Quality Assurance
          </h1>
          <p className="mt-3 max-w-4xl text-sm leading-relaxed text-slate-600">
            Analisi automatica attraverso architettura multi-agentica per tutti
            i syllabus all'interno dell'Università Degli Studi di Catania.
          </p>
        </div>
        <StatsStrip />
      </header>

      <Section title="Selezione corso">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Dipartimento
            </label>
            <DepartmentSelector
              value={departmentId}
              onChange={handleDepartmentChange}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Corso di laurea
            </label>
            <CdlSelector
              departmentId={departmentId}
              value={cdlId}
              onChange={handleCdlChange}
            />
          </div>
        </div>
      </Section>

      <div ref={syllabiRef} className="scroll-mt-4">
        <SyllabiTable cdlId={cdlId} />
      </div>
    </div>
  );
}

function parseUrlId(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

// ---------------------------------------------------------------------------
// Stats strip — mirrors the EvaluationPage KPI treatment.
// ---------------------------------------------------------------------------

type StatTone = "info" | "success" | "default";

function StatsStrip() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  const englishCoverage =
    stats && stats.syllabi > 0
      ? Math.round((stats.with_english / stats.syllabi) * 100)
      : 0;

  return (
    <dl className="grid w-full grid-cols-2 gap-5 border-y border-slate-200 py-4 md:grid-cols-4 md:gap-8 xl:gap-12">
      <StatItem
        label="Syllabi"
        value={stats?.syllabi ?? "—"}
        hint="totali in archivio"
        icon={<BookOpen className="h-3.5 w-3.5" aria-hidden />}
        tone="info"
      />
      <StatItem
        label="Versione EN"
        value={stats ? `${englishCoverage}%` : "—"}
        hint={stats ? `${stats.with_english} bilingui` : "in attesa"}
        icon={<Languages className="h-3.5 w-3.5" aria-hidden />}
        tone="success"
      />
      <StatItem
        label="CdL"
        value={stats?.cdl ?? "—"}
        hint="corsi di laurea"
        icon={<GraduationCap className="h-3.5 w-3.5" aria-hidden />}
        tone="default"
      />
      <StatItem
        label="Dipartimenti"
        value={stats?.departments ?? "—"}
        hint="fonti monitorate"
        icon={<Building2 className="h-3.5 w-3.5" aria-hidden />}
        tone="default"
      />
    </dl>
  );
}

function StatItem({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone: StatTone;
}) {
  const valueColor =
    tone === "success"
      ? "text-emerald-700"
      : tone === "info"
        ? "text-sky-800"
        : "text-slate-950";
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
        {icon ? <span aria-hidden>{icon}</span> : null}
        {label}
      </dt>
      <dd
        className={`mt-1.5 text-2xl font-semibold leading-none tabular-nums ${valueColor}`}
      >
        {value}
      </dd>
      {hint ? (
        <dd className="mt-1 text-[11px] text-slate-500">{hint}</dd>
      ) : null}
    </div>
  );
}

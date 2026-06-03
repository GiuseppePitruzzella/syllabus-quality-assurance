import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Building2,
  GraduationCap,
  Languages,
} from "lucide-react";

import { Navbar } from "@/components/Sidebar";
import { Section } from "@/components/layout/Section";
import { getStats } from "@/lib/api";

import { CdlSelector } from "./CdlSelector";
import { DepartmentSelector } from "./DepartmentSelector";
import { SyllabiTable } from "./SyllabiTable";

/**
 * Phase 6.1.E — SaaS shell dashboard with the stats strip
 * integrated into the dark chrome.
 *
 *   1. Dark rounded shell (slate-800): navbar, then hero (badge /
 *      title / description / status pill), then a four-tile stats
 *      strip directly inside the same shell. No separate metrics
 *      row below.
 *
 *   2. `Selezione corso`.
 *
 *   3. `Elenco insegnamenti` — scrolled into view when the user
 *      picks a CdL.
 */
export function Dashboard() {
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [cdlId, setCdlId] = useState<number | null>(null);
  const syllabiRef = useRef<HTMLDivElement>(null);

  function handleDepartmentChange(id: number | null) {
    setDepartmentId(id);
    setCdlId(null);
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
    <div className="space-y-4 px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8">
      <header className="overflow-hidden rounded-2xl bg-slate-800 text-slate-100">
        <Navbar />
        <div className="px-6 pb-10 pt-8 sm:px-10 sm:pb-12 sm:pt-10">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0">
              <span className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-300">
                Qualità syllabus
              </span>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white md:text-4xl">
                Syllabus Quality Assurance
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">
                Strumento di supporto alla revisione della qualità dei syllabus
                universitari, con analisi bilingue, criteri C1-C9 e report
                consultabili.
              </p>
            </div>
            <span className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-md border border-emerald-400/20 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-200 sm:self-end">
              <span
                aria-hidden
                className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400"
              />
              Valutazione attiva
            </span>
          </div>
        </div>
        <DarkStatsStrip />
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
              onChange={setCdlId}
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

// ---------------------------------------------------------------------------
// Dark stats strip — four-tile row living inside the hero shell.
// ---------------------------------------------------------------------------

type DarkTone = "info" | "success" | "default";

function DarkStatsStrip() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  const englishCoverage =
    stats && stats.syllabi > 0
      ? Math.round((stats.with_english / stats.syllabi) * 100)
      : 0;

  return (
    <div className="grid grid-cols-2 divide-x divide-white/10 border-t border-white/10 sm:grid-cols-4">
      <DarkTile
        label="Syllabi"
        value={stats?.syllabi ?? "—"}
        hint="totali in archivio"
        icon={<BookOpen className="h-3.5 w-3.5" aria-hidden />}
        tone="info"
      />
      <DarkTile
        label="Versione EN"
        value={stats ? `${englishCoverage}%` : "—"}
        hint={stats ? `${stats.with_english} bilingui` : "in attesa"}
        icon={<Languages className="h-3.5 w-3.5" aria-hidden />}
        tone="success"
      />
      <DarkTile
        label="CdL"
        value={stats?.cdl ?? "—"}
        hint="corsi di laurea"
        icon={<GraduationCap className="h-3.5 w-3.5" aria-hidden />}
        tone="default"
      />
      <DarkTile
        label="Dipartimenti"
        value={stats?.departments ?? "—"}
        hint="fonti monitorate"
        icon={<Building2 className="h-3.5 w-3.5" aria-hidden />}
        tone="default"
      />
    </div>
  );
}

function DarkTile({
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
  tone: DarkTone;
}) {
  const valueColor =
    tone === "success"
      ? "text-emerald-300"
      : tone === "info"
        ? "text-cyan-300"
        : "text-white";
  return (
    <div className="px-6 py-4 sm:px-8 sm:py-5">
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {icon ? <span aria-hidden>{icon}</span> : null}
        {label}
      </div>
      <p
        className={`mt-1.5 text-2xl font-semibold leading-none tabular-nums ${valueColor}`}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-1 text-[11px] text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}

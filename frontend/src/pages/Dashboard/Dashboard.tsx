import { useState } from "react";

import { Navbar } from "@/components/Sidebar";
import { Section } from "@/components/layout/Section";

import { CdlSelector } from "./CdlSelector";
import { DepartmentSelector } from "./DepartmentSelector";
import { StatsCards } from "./StatsCards";
import { SyllabiTable } from "./SyllabiTable";

/**
 * Phase 6.1.B (rev) — SaaS shell dashboard, full-width.
 *
 * Top to bottom, no max-width clamp on the page:
 *
 *   1. Dark rounded shell — one rounded-2xl slate-950 block holding
 *      the inline `Navbar` + the hero. `overflow-hidden` clips the
 *      navbar's square corners into the shell so there is no seam
 *      between navbar and hero.
 *
 *   2. Metrics row — four white tiles on a plain row, no overlap.
 *
 *   3. `Selezione corso` + `Elenco insegnamenti` stacked, both
 *      full-width.
 */
export function Dashboard() {
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [cdlId, setCdlId] = useState<number | null>(null);

  function handleDepartmentChange(id: number | null) {
    setDepartmentId(id);
    setCdlId(null);
  }

  return (
    <div className="space-y-4 px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8">
      <header className="overflow-hidden rounded-2xl bg-slate-950 text-slate-100">
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
            <span className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300 sm:self-end">
              <span
                aria-hidden
                className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400"
              />
              Valutazione attiva
            </span>
          </div>
        </div>
      </header>

      <StatsCards />

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

      <SyllabiTable cdlId={cdlId} />
    </div>
  );
}

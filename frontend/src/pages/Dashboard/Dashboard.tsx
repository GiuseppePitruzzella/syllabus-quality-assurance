import { useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Section } from "@/components/layout/Section";

import { CdlSelector } from "./CdlSelector";
import { DepartmentSelector } from "./DepartmentSelector";
import { StatsCards } from "./StatsCards";
import { SyllabiTable } from "./SyllabiTable";

export function Dashboard() {
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [cdlId, setCdlId] = useState<number | null>(null);

  function handleDepartmentChange(id: number | null) {
    setDepartmentId(id);
    setCdlId(null);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHeader
        badge="Qualità syllabus"
        title="Cruscotto didattico"
        subtitle="Stato dell'archivio, copertura bilingue e revisioni disponibili."
        actions={
          <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-800">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500"
              aria-hidden
            />
            Valutazione attiva
          </span>
        }
      />

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

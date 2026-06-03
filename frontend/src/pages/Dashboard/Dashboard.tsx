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
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        badge="Qualità syllabus"
        title="Cruscotto didattico"
        subtitle="Panoramica operativa dei syllabus, dei contenuti bilingui e delle revisioni disponibili."
        actions={
          <span className="rounded-md border border-emerald-200 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-800">
            Valutazione attiva
          </span>
        }
      />

      <Section title="Selezione corso">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Dipartimento
            </label>
            <DepartmentSelector
              value={departmentId}
              onChange={handleDepartmentChange}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
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

      <StatsCards />

      <SyllabiTable cdlId={cdlId} />
    </div>
  );
}

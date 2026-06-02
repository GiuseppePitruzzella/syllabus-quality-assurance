import { useState } from "react";
import { DepartmentSelector } from "./DepartmentSelector";
import { CdlSelector } from "./CdlSelector";
import { SyllabiTable } from "./SyllabiTable";
import { StatsCards } from "./StatsCards";
import { Badge } from "@/components/ui/badge";

export function Dashboard() {
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [cdlId, setCdlId] = useState<number | null>(null);

  function handleDepartmentChange(id: number | null) {
    setDepartmentId(id);
    setCdlId(null);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b pb-5">
        <div className="min-w-0">
          <Badge
            variant="outline"
            className="mb-3 border-cyan-200 bg-cyan-500/10 text-cyan-800"
          >
            Qualità syllabus
          </Badge>
          <h1 className="!my-0 !text-3xl !font-semibold !tracking-normal md:!text-4xl">
            Cruscotto didattico
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Panoramica operativa dei syllabus, dei contenuti bilingui e delle
            revisioni disponibili.
          </p>
        </div>
        <div className="rounded-md border border-emerald-200 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-800">
          Valutazione attiva
        </div>
      </header>

      <section className="rounded-lg border bg-card">
        <div className="border-b px-4 py-3">
          <h2 className="!m-0 !text-base !font-semibold !tracking-normal">
            Selezione corso
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
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
      </section>

      <StatsCards />

      <SyllabiTable cdlId={cdlId} />
    </div>
  );
}

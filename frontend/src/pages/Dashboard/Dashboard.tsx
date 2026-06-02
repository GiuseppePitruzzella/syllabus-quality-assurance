import { useState } from "react";
import { DepartmentSelector } from "./DepartmentSelector";
import { CdlSelector } from "./CdlSelector";
import { SyllabiTable } from "./SyllabiTable";
import { StatsCards } from "./StatsCards";

export function Dashboard() {
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [cdlId, setCdlId] = useState<number | null>(null);

  function handleDepartmentChange(id: number | null) {
    setDepartmentId(id);
    setCdlId(null);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
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
            Corso di Laurea
          </label>
          <CdlSelector
            departmentId={departmentId}
            value={cdlId}
            onChange={setCdlId}
          />
        </div>
      </div>

      <SyllabiTable cdlId={cdlId} />

      <StatsCards />
    </div>
  );
}

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
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">Dipartimento</label>
          <DepartmentSelector
            value={departmentId}
            onChange={handleDepartmentChange}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Corso di Laurea</label>
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

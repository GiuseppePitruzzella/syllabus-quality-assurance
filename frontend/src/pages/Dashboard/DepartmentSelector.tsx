import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2 } from "lucide-react";

import { getDepartments, scrapeDepartments } from "@/lib/api";
import { useScrapeJob } from "@/hooks/useScrapeJob";
import { EmptyState } from "@/components/EmptyState";
import { ScrapeProgress } from "@/components/ScrapeProgress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TRIGGER_CLASS =
  "h-12 w-full rounded-xl border-input bg-card px-4 text-sm font-medium shadow-xs transition-all hover:border-primary/40 hover:bg-primary/[0.03] focus-visible:border-primary data-[popup-open]:border-primary data-[popup-open]:ring-2 data-[popup-open]:ring-primary/20 [&_svg]:size-4";

interface DepartmentSelectorProps {
  value: number | null;
  onChange: (id: number | null) => void;
}

export function DepartmentSelector({
  value,
  onChange,
}: DepartmentSelectorProps) {
  const queryClient = useQueryClient();

  const scrapeJob = useScrapeJob(() => {
    queryClient.invalidateQueries({ queryKey: ["departments"] });
  });

  const { data: departments = [], isLoading } = useQuery({
    queryKey: ["departments"],
    queryFn: getDepartments,
  });

  async function handleScrape() {
    const { job_id } = await scrapeDepartments();
    scrapeJob.start(job_id);
  }

  if (scrapeJob.status === "running") {
    return (
      <ScrapeProgress
        current={scrapeJob.current}
        total={scrapeJob.total}
        message={scrapeJob.message}
      />
    );
  }

  if (!isLoading && departments.length === 0 && scrapeJob.status === "idle") {
    return (
      <EmptyState
        message="Nessun dipartimento trovato."
        buttonLabel="Scarica Dipartimenti"
        onAction={handleScrape}
      />
    );
  }

  const selectedName = departments.find((d) => d.id === value)?.name;

  return (
    <Select
      value={value !== null ? String(value) : null}
      onValueChange={(v) => onChange(v !== null ? Number(v) : null)}
    >
      <SelectTrigger
        aria-label="Dipartimento"
        className={TRIGGER_CLASS}
      >
        <Building2
          className="text-muted-foreground"
          aria-hidden
        />
        <SelectValue placeholder="Seleziona un dipartimento">
          {selectedName}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {departments.map((dept) => (
          <SelectItem key={dept.id} value={String(dept.id)}>
            {dept.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

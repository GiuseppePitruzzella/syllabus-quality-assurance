import { useQuery, useQueryClient } from "@tanstack/react-query";
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
      <SelectTrigger className="h-11 w-full rounded-xl bg-card px-4 text-sm font-medium hover:border-primary/40">
        <SelectValue placeholder="Seleziona dipartimento...">
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

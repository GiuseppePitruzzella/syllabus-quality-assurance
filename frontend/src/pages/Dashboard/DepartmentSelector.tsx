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
import {
  selectFieldContent,
  selectFieldItem,
  selectFieldTrigger,
} from "@/components/ui/select-field";
import { cn } from "@/lib/utils";

const TRIGGER_CLASS = cn(selectFieldTrigger, "h-12 w-full");
const CONTENT_CLASS = selectFieldContent;
const ITEM_CLASS = selectFieldItem;

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
      <SelectContent className={CONTENT_CLASS}>
        {departments.map((dept) => (
          <SelectItem
            key={dept.id}
            value={String(dept.id)}
            className={ITEM_CLASS}
          >
            {dept.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

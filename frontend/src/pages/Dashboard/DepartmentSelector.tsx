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
  "h-12 w-full justify-start rounded-none border-x-0 border-t-0 border-b border-slate-300 bg-transparent px-0 text-sm font-medium text-slate-950 shadow-none transition-colors hover:border-slate-500 hover:bg-transparent focus-visible:border-slate-950 focus-visible:ring-0 data-[popup-open]:border-slate-950 data-[popup-open]:ring-0 disabled:bg-transparent disabled:text-slate-400 data-placeholder:text-sm data-placeholder:font-normal [&_svg]:size-4";

const CONTENT_CLASS =
  "rounded-none shadow-lg ring-1 ring-slate-200";

const ITEM_CLASS =
  "rounded-none px-2 py-2 focus:bg-slate-100 focus:text-slate-950";

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

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getCdl, scrapeCdl } from "@/lib/api";
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

interface CdlSelectorProps {
  departmentId: number | null;
  value: number | null;
  onChange: (id: number | null) => void;
}

export function CdlSelector({
  departmentId,
  value,
  onChange,
}: CdlSelectorProps) {
  const queryClient = useQueryClient();

  const scrapeJob = useScrapeJob(() => {
    queryClient.invalidateQueries({ queryKey: ["cdl", departmentId] });
  });

  const { data: cdlList = [], isLoading } = useQuery({
    queryKey: ["cdl", departmentId],
    queryFn: () => getCdl(departmentId!),
    enabled: departmentId !== null,
  });

  async function handleScrape() {
    if (departmentId === null) return;
    const { job_id } = await scrapeCdl(departmentId);
    scrapeJob.start(job_id);
  }

  if (departmentId === null) {
    return (
      <Select disabled>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Seleziona prima un dipartimento..." />
        </SelectTrigger>
        <SelectContent />
      </Select>
    );
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

  if (!isLoading && cdlList.length === 0 && scrapeJob.status === "idle") {
    return (
      <EmptyState
        message="Nessun CdL trovato per questo dipartimento."
        buttonLabel="Scarica CdL"
        onAction={handleScrape}
      />
    );
  }

  return (
    <Select
      value={value}
      onValueChange={(v) => onChange(v)}
    >
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Seleziona CdL..." />
      </SelectTrigger>
      <SelectContent>
        {cdlList.map((cdl) => (
          <SelectItem key={cdl.id} value={cdl.id}>
            <span className="text-xs text-muted-foreground mr-1.5">
              {cdl.type}
            </span>
            {cdl.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";

import { getCdl, scrapeCdl } from "@/lib/api";
import { useScrapeJob } from "@/hooks/useScrapeJob";
import { CdlTypeBadge } from "@/components/CdlTypeBadge";
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
        <SelectTrigger
          aria-label="Corso di laurea"
          className={TRIGGER_CLASS}
        >
          <GraduationCap
            className="text-muted-foreground"
            aria-hidden
          />
          <SelectValue placeholder="Seleziona prima un dipartimento" />
        </SelectTrigger>
        <SelectContent className={CONTENT_CLASS} />
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

  const selected = cdlList.find((c) => c.id === value);

  return (
    <Select
      value={value !== null ? String(value) : null}
      onValueChange={(v) => onChange(v !== null ? Number(v) : null)}
    >
      <SelectTrigger
        aria-label="Corso di laurea"
        className={TRIGGER_CLASS}
      >
        <GraduationCap
          className="text-muted-foreground"
          aria-hidden
        />
        <SelectValue placeholder="Seleziona un corso di laurea">
          {selected && (
            <span className="flex items-center gap-2">
              <CdlTypeBadge type={selected.type} />
              {selected.name}
            </span>
          )}
        </SelectValue>
      </SelectTrigger>
      <SelectContent className={CONTENT_CLASS}>
        {cdlList.map((cdl) => (
          <SelectItem
            key={cdl.id}
            value={String(cdl.id)}
            className={ITEM_CLASS}
          >
            <span className="flex items-center gap-2">
              <CdlTypeBadge type={cdl.type} />
              {cdl.name}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";

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

const TRIGGER_CLASS =
  "h-12 w-full rounded-xl border-input bg-card px-4 text-sm font-medium shadow-xs transition-all hover:border-primary/40 hover:bg-primary/[0.03] focus-visible:border-primary data-[popup-open]:border-primary data-[popup-open]:ring-2 data-[popup-open]:ring-primary/20 [&_svg]:size-4";

interface CdlSelectorProps {
  departmentId: number | null;
  value: number | null;
  onChange: (id: number | null) => void;
}

function CdlTypeBadge({ type }: { type: string }) {
  const isTriennale = type.toLowerCase().includes("triennale");
  return (
    <span
      className={`inline-flex w-14 items-center justify-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        isTriennale
          ? "bg-accent/15 text-accent"
          : "bg-primary/10 text-primary"
      }`}
    >
      {isTriennale ? "L" : "LM"}
    </span>
  );
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
      <SelectContent>
        {cdlList.map((cdl) => (
          <SelectItem key={cdl.id} value={String(cdl.id)}>
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

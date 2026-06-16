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
  "h-12 w-full justify-start rounded-none border-x-0 border-t-0 border-b border-slate-300 bg-transparent px-0 text-sm font-medium text-slate-950 shadow-none transition-colors hover:border-slate-500 hover:bg-transparent focus-visible:border-slate-950 focus-visible:ring-0 data-[popup-open]:border-slate-950 data-[popup-open]:ring-0 disabled:bg-transparent disabled:text-slate-400 data-placeholder:text-sm data-placeholder:font-normal [&_svg]:size-4";

const CONTENT_CLASS =
  "rounded-none shadow-lg ring-1 ring-slate-200";

const ITEM_CLASS =
  "rounded-none px-2 py-2 focus:bg-slate-100 focus:text-slate-950";

interface CdlSelectorProps {
  departmentId: number | null;
  value: number | null;
  onChange: (id: number | null) => void;
}

function CdlTypeBadge({ type }: { type: string }) {
  const isTriennale = type.toLowerCase().includes("triennale");
  return (
    <span
      className={`inline-flex w-8 items-center justify-center font-mono text-[11px] font-semibold uppercase tracking-wide ${
        isTriennale
          ? "text-emerald-700"
          : "text-sky-800"
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

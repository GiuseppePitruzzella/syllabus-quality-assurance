import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ArrowRight, RefreshCw, Search } from "lucide-react";

import { getSyllabi, scrapeSyllabiList } from "@/lib/api";
import { useScrapeJob } from "@/hooks/useScrapeJob";
import { EmptyState } from "@/components/EmptyState";
import { ScrapeProgress } from "@/components/ScrapeProgress";
import { Section } from "@/components/layout/Section";
import { Toolbar } from "@/components/layout/Toolbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface SyllabiTableProps {
  cdlId: number | null;
}

export function SyllabiTable({ cdlId }: SyllabiTableProps) {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const scrapeJob = useScrapeJob(() => {
    queryClient.invalidateQueries({ queryKey: ["syllabi", cdlId] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
  });

  const { data: syllabi = [], isLoading } = useQuery({
    queryKey: ["syllabi", cdlId, search],
    queryFn: () => getSyllabi(cdlId!, search || undefined),
    enabled: cdlId !== null,
  });

  async function handleScrape() {
    if (cdlId === null) return;
    const { job_id } = await scrapeSyllabiList(cdlId);
    scrapeJob.start(job_id);
  }

  if (cdlId === null) {
    return (
      <Section
        title="Elenco insegnamenti"
        description="Nessun corso di laurea selezionato"
      >
        {null}
      </Section>
    );
  }

  if (scrapeJob.status === "running") {
    return (
      <Section
        title="Elenco insegnamenti"
        description="Aggiornamento in corso"
      >
        <ScrapeProgress
          current={scrapeJob.current}
          total={scrapeJob.total}
          message={scrapeJob.message}
        />
      </Section>
    );
  }

  if (
    !isLoading &&
    syllabi.length === 0 &&
    !search &&
    scrapeJob.status === "idle"
  ) {
    return (
      <Section
        title="Elenco insegnamenti"
        description="Archivio CdL vuoto"
      >
        <EmptyState
          message="Nessun syllabus trovato per questo CdL."
          buttonLabel="Scarica syllabus"
          onAction={handleScrape}
        />
      </Section>
    );
  }

  return (
    <Section
      title={
        <span className="flex items-center gap-2">
          Elenco insegnamenti
          <span className="bg-muted px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
            {syllabi.length}
          </span>
        </span>
      }
      description={
        search ? "Risultati filtrati" : "Syllabus disponibili per il CdL"
      }
      padded={false}
    >
      <div className="pt-2">
        <Toolbar
          actions={
            <Button
              variant="ghost"
              onClick={handleScrape}
              className="rounded-none px-0 text-xs font-medium text-slate-600 shadow-none hover:bg-transparent hover:text-slate-950"
            >
              <RefreshCw className="h-4 w-4" />
              Aggiorna elenco
            </Button>
          }
        >
          <div className="relative min-w-64">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Cerca insegnamento"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>
        </Toolbar>
      </div>

      <Table className="w-full table-fixed">
        <TableHeader>
          <TableRow className="bg-transparent hover:bg-transparent">
            <TableHead className="w-16 text-center">Anno</TableHead>
            <TableHead className="w-24">Codice</TableHead>
            <TableHead>Insegnamento</TableHead>
            <TableHead className="w-28 text-center">Lingua</TableHead>
            <TableHead className="w-56">Docente</TableHead>
            <TableHead className="w-24 text-right">Azione</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <LoadingRows />
          ) : (
            syllabi.map((syl) => (
              <TableRow key={syl.id} className="hover:bg-muted/40">
                <TableCell className="text-center">
                  <span className="inline-flex min-w-7 items-center justify-center bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">
                    {syl.year_of_study || "—"}
                  </span>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {syl.course_code || "—"}
                </TableCell>
                <TableCell className="min-w-0">
                  <div className="truncate font-medium text-foreground">
                    {syl.course_name}
                  </div>
                  {syl.module && (
                    <div className="mt-0.5 truncate text-xs text-muted-foreground">
                      Modulo: {syl.module}
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-center">
                  <LanguageBadge hasEnglish={syl.has_english} />
                </TableCell>
                <TableCell className="truncate text-sm text-muted-foreground">
                  {syl.teacher || "—"}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => navigate(`/syllabus/${syl.seuid}`)}
                  >
                    Apri
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </Section>
  );
}

function LanguageBadge({ hasEnglish }: { hasEnglish: boolean }) {
  return hasEnglish ? (
    <span className="inline-flex bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-800">
      IT + EN
    </span>
  ) : (
    <span className="inline-flex bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-800">
      Solo IT
    </span>
  );
}

function LoadingRows() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, index) => (
        <TableRow key={index}>
          <TableCell colSpan={6}>
            <div className="h-8 animate-pulse rounded bg-muted" />
          </TableCell>
        </TableRow>
      ))}
    </>
  );
}

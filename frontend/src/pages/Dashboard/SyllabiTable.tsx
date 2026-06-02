import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getSyllabi, scrapeSyllabiList } from "@/lib/api";
import { useScrapeJob } from "@/hooks/useScrapeJob";
import { EmptyState } from "@/components/EmptyState";
import { ScrapeProgress } from "@/components/ScrapeProgress";
import { Badge } from "@/components/ui/badge";
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
import { ArrowRight, RefreshCw, Search } from "lucide-react";

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
      <section className="rounded-lg border bg-card">
        <SectionHeader
          title="Elenco insegnamenti"
          subtitle="Nessun corso di laurea selezionato"
        />
      </section>
    );
  }

  if (scrapeJob.status === "running") {
    return (
      <section className="rounded-lg border bg-card">
        <SectionHeader title="Elenco insegnamenti" subtitle="Aggiornamento in corso" />
        <div className="p-4">
          <ScrapeProgress
            current={scrapeJob.current}
            total={scrapeJob.total}
            message={scrapeJob.message}
          />
        </div>
      </section>
    );
  }

  if (!isLoading && syllabi.length === 0 && !search && scrapeJob.status === "idle") {
    return (
      <section className="rounded-lg border bg-card">
        <SectionHeader title="Elenco insegnamenti" subtitle="Archivio CdL vuoto" />
        <div className="p-4">
          <EmptyState
            message="Nessun syllabus trovato per questo CdL."
            buttonLabel="Scarica syllabus"
            onAction={handleScrape}
          />
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="!m-0 !text-base !font-semibold !tracking-normal">
              Elenco insegnamenti
            </h2>
            <Badge variant="outline" className="bg-muted/50">
              {syllabi.length}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {search ? "Risultati filtrati" : "Syllabus disponibili per il CdL"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-64">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Cerca insegnamento"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>
          <Button variant="outline" onClick={handleScrape}>
            <RefreshCw className="h-4 w-4" />
            Aggiorna elenco
          </Button>
        </div>
      </div>

      <Table className="w-full table-fixed">
        <TableHeader>
          <TableRow className="bg-muted/30 hover:bg-muted/30">
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
              <TableRow key={syl.id} className="hover:bg-cyan-500/5">
                <TableCell className="text-center">
                  <Badge
                    variant="outline"
                    className="border-slate-200 bg-slate-500/10 text-slate-700"
                  >
                    {syl.year_of_study || "—"}
                  </Badge>
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
    </section>
  );
}

function SectionHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="border-b px-4 py-3">
      <h2 className="!m-0 !text-base !font-semibold !tracking-normal">
        {title}
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
    </div>
  );
}

function LanguageBadge({ hasEnglish }: { hasEnglish: boolean }) {
  return hasEnglish ? (
    <Badge
      variant="outline"
      className="border-emerald-200 bg-emerald-500/10 text-emerald-800"
    >
      IT + EN
    </Badge>
  ) : (
    <Badge
      variant="outline"
      className="border-amber-200 bg-amber-500/10 text-amber-800"
    >
      Solo IT
    </Badge>
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

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getSyllabi, scrapeSyllabiList } from "@/lib/api";
import { useScrapeJob } from "@/hooks/useScrapeJob";
import { EmptyState } from "@/components/EmptyState";
import { ScrapeProgress } from "@/components/ScrapeProgress";
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

  if (cdlId === null) return null;

  async function handleScrape() {
    if (cdlId === null) return;
    const { job_id } = await scrapeSyllabiList(cdlId);
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

  if (!isLoading && syllabi.length === 0 && !search && scrapeJob.status === "idle") {
    return (
      <EmptyState
        message="Nessun syllabus trovato per questo CdL."
        buttonLabel="Scarica Syllabi"
        onAction={handleScrape}
      />
    );
  }

  return (
    <div className="space-y-4">
      <Input
        placeholder="Cerca insegnamento..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />
      <Table className="table-fixed w-full">
        <TableHeader>
          <TableRow>
            <TableHead className="w-12 text-center">Anno</TableHead>
            <TableHead>Insegnamento</TableHead>
            <TableHead className="w-48 text-right">Docente</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {syllabi.map((syl) => (
            <TableRow
              key={syl.id}
              className="cursor-pointer"
              onClick={() => navigate(`/syllabus/${syl.seuid}`)}
            >
              <TableCell className="text-center text-muted-foreground text-xs">
                {syl.year_of_study}
              </TableCell>
              <TableCell className="font-medium truncate">
                {syl.course_name}
              </TableCell>
              <TableCell className="text-right text-muted-foreground text-sm truncate">
                {syl.teacher}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

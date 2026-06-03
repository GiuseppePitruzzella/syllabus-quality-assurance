import { Section } from "@/components/layout/Section";
import type { SyllabusDetail } from "@/lib/types";

interface MetadataSidebarProps {
  data: SyllabusDetail;
}

/**
 * Phase 5.9.B — full-width metadata strip.
 *
 * Replaces the previous right-side Card sidebar with a compact dense
 * strip below the header. The strip lists the slow-changing facts
 * about the syllabus (codice, anno accademico, dipartimento, last
 * scrape) while teacher / CdL / academic year live in the header
 * subtitle to avoid duplication.
 *
 * Component name is preserved (`MetadataSidebar`) so the import in
 * SyllabusViewer is untouched; semantically it's a strip now.
 */
export function MetadataSidebar({ data }: MetadataSidebarProps) {
  const scrapedAt = data.scraped_at ? new Date(data.scraped_at) : null;

  const fields: { label: string; value: React.ReactNode }[] = [
    {
      label: "Codice",
      value: (
        <code className="font-mono text-sm">{data.course_code || "—"}</code>
      ),
    },
    { label: "Anno accademico", value: data.academic_year || "—" },
    {
      label: "Anno di studio",
      value: data.year_of_study ? `${data.year_of_study}° anno` : "—",
    },
    { label: "Dipartimento", value: data.department_name || "—" },
    { label: "Corso di laurea", value: data.cdl_name || "—" },
    {
      label: "Aggiornato",
      value: scrapedAt ? formatDate(scrapedAt) : "—",
    },
  ];

  return (
    <Section title="Metadati" padded={false}>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 p-4 sm:grid-cols-3 lg:grid-cols-6">
        {fields.map((f) => (
          <div key={f.label} className="min-w-0">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {f.label}
            </dt>
            <dd className="mt-0.5 truncate text-sm text-foreground">
              {f.value}
            </dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

function formatDate(d: Date): string {
  return d.toLocaleDateString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

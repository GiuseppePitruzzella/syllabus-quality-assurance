import { useQuery } from "@tanstack/react-query";
import { getStats } from "@/lib/api";
import { BookOpen, Building2, GraduationCap, Languages } from "lucide-react";

export function StatsCards() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  if (!stats) return null;

  const englishCoverage =
    stats.syllabi > 0 ? Math.round((stats.with_english / stats.syllabi) * 100) : 0;

  const items = [
    {
      label: "Syllabi",
      value: stats.syllabi,
      detail: "totali in archivio",
      icon: BookOpen,
      tone: "border-cyan-300 bg-cyan-500/10 text-cyan-800",
    },
    {
      label: "Versione EN",
      value: `${englishCoverage}%`,
      detail: `${stats.with_english} syllabus bilingui`,
      icon: Languages,
      tone: "border-emerald-300 bg-emerald-500/10 text-emerald-800",
    },
    {
      label: "CdL",
      value: stats.cdl,
      detail: "corsi di laurea",
      icon: GraduationCap,
      tone: "border-violet-300 bg-violet-500/10 text-violet-800",
    },
    {
      label: "Dipartimenti",
      value: stats.departments,
      detail: "fonti monitorate",
      icon: Building2,
      tone: "border-amber-300 bg-amber-500/10 text-amber-800",
    },
  ];

  return (
    <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3"
        >
          <div className={`rounded-md border p-2 ${item.tone}`}>
            <item.icon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {item.label}
            </p>
            <p className="text-2xl font-semibold tabular-nums text-foreground">
              {item.value}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {item.detail}
            </p>
          </div>
        </div>
      ))}
    </section>
  );
}

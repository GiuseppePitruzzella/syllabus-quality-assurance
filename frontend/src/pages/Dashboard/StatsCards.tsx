import { useQuery } from "@tanstack/react-query";
import { BookOpen, Building2, GraduationCap, Languages } from "lucide-react";

import { MetricTile } from "@/components/layout/MetricTile";
import { getStats } from "@/lib/api";

/**
 * Phase 6.0.C — homepage stats migrated to the MetricTile primitive.
 *
 * Tone choices follow the charter:
 *   - Syllabi   : info     (cyan)   — primary archive counter
 *   - EN cov.   : success  (emerald)— positive coverage signal
 *   - CdL       : muted    (card)   — structural counter, no signal
 *   - Dept.     : muted    (card)   — structural counter, no signal
 *
 * Two of the four tiles are intentionally muted: the previous version
 * coloured all four (cyan/emerald/violet/amber) which read more as
 * decoration than as semantic. The new palette uses colour only when
 * it carries meaning ("there are syllabi", "EN coverage is positive").
 */
export function StatsCards() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  if (!stats) return null;

  const englishCoverage =
    stats.syllabi > 0
      ? Math.round((stats.with_english / stats.syllabi) * 100)
      : 0;

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <MetricTile
        label="Syllabi"
        value={stats.syllabi}
        hint="totali in archivio"
        icon={<BookOpen className="h-3.5 w-3.5" aria-hidden />}
        tone="info"
      />
      <MetricTile
        label="Versione EN"
        value={`${englishCoverage}%`}
        hint={`${stats.with_english} bilingui`}
        icon={<Languages className="h-3.5 w-3.5" aria-hidden />}
        tone="success"
      />
      <MetricTile
        label="CdL"
        value={stats.cdl}
        hint="corsi di laurea"
        icon={<GraduationCap className="h-3.5 w-3.5" aria-hidden />}
        tone="muted"
      />
      <MetricTile
        label="Dipartimenti"
        value={stats.departments}
        hint="fonti monitorate"
        icon={<Building2 className="h-3.5 w-3.5" aria-hidden />}
        tone="muted"
      />
    </div>
  );
}

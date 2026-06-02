import type { ScheduleItem } from "@/lib/types";

interface CourseScheduleTableProps {
  items: ScheduleItem[] | null;
}

/**
 * Phase 5.9.B — denser schedule table.
 *
 * Drops the shadcn Table primitive in favour of a hand-rolled table
 * with thin borders and tighter padding. The fallback chain on
 * topic / references is unchanged: ``argomenti / subjects / ...`` and
 * ``riferimenti_testi / text_references / ...`` so EN schedule
 * tables (English SmartEdu headers) render content instead of empty
 * cells.
 */
export function CourseScheduleTable({ items }: CourseScheduleTableProps) {
  if (!items || items.length === 0) {
    return (
      <p className="rounded-md border border-dashed px-3 py-3 text-sm text-muted-foreground">
        Nessuna programmazione disponibile.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="w-12 px-3 py-2 text-left font-medium">N°</th>
            <th className="px-3 py-2 text-left font-medium">Argomento</th>
            <th className="px-3 py-2 text-left font-medium">Riferimenti</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => {
            const topic =
              item.argomenti ??
              item.subjects ??
              item.subject ??
              item.topics ??
              item.topic ??
              "";
            const references =
              item.riferimenti_testi ??
              item.text_references ??
              item.textbook_references ??
              item.references ??
              "";

            return (
              <tr key={i} className="border-t">
                <td className="px-3 py-2 align-top tabular-nums text-muted-foreground">
                  {item.numero ?? i + 1}
                </td>
                <td className="px-3 py-2 align-top">{topic || "—"}</td>
                <td className="px-3 py-2 align-top text-muted-foreground">
                  {references || "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

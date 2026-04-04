import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ScheduleItem } from "@/lib/types";

interface CourseScheduleTableProps {
  items: ScheduleItem[] | null;
}

export function CourseScheduleTable({ items }: CourseScheduleTableProps) {
  if (!items || items.length === 0) {
    return (
      <p className="text-muted-foreground">
        Nessuna programmazione disponibile.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">N°</TableHead>
          <TableHead>Argomento</TableHead>
          <TableHead>Riferimenti</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item, i) => (
          <TableRow key={i}>
            <TableCell>{item.numero}</TableCell>
            <TableCell className="whitespace-normal">
              {item.argomenti}
            </TableCell>
            <TableCell className="whitespace-normal">
              {item.riferimenti_testi}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

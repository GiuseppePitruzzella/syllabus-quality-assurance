import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { FlaskConical } from "lucide-react";
import type { SyllabusDetail } from "@/lib/types";

interface MetadataSidebarProps {
  data: SyllabusDetail;
}

const fields: { label: string; key: keyof SyllabusDetail; suffix?: string }[] =
  [
    { label: "Codice", key: "course_code" },
    { label: "Docente", key: "teacher" },
    { label: "Anno accademico", key: "academic_year" },
    { label: "Anno di studio", key: "year_of_study", suffix: "° anno" },
    { label: "Corso di Laurea", key: "cdl_name" },
    { label: "Dipartimento", key: "department_name" },
  ];

export function MetadataSidebar({ data }: MetadataSidebarProps) {
  return (
    <Card className="w-72 shrink-0">
      <CardHeader>
        <CardTitle>Dettagli</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {fields.map((f) => {
          const value = data[f.key];
          return (
            <div key={f.key}>
              <p className="text-xs text-muted-foreground">{f.label}</p>
              <p className="font-medium">
                {value != null ? `${value}${f.suffix ?? ""}` : "\u2014"}
              </p>
            </div>
          );
        })}
        {data.module && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Modulo</p>
            <Badge variant="secondary">{data.module}</Badge>
          </div>
        )}
        <div className="pt-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button variant="outline" className="w-full" disabled>
                    <FlaskConical className="mr-2 h-4 w-4" />
                    Evaluate
                  </Button>
                }
              />
              <TooltipContent>
                Coming soon — Multi-agent evaluation pipeline
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </CardContent>
    </Card>
  );
}

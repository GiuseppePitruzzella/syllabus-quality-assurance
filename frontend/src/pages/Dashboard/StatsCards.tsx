import { useQuery } from "@tanstack/react-query";
import { getStats } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { BookOpen, Globe, Building2 } from "lucide-react";

export function StatsCards() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  if (!stats) return null;

  const items = [
    { label: "Syllabi totali", value: stats.syllabi, icon: BookOpen },
    { label: "Con versione inglese", value: stats.with_english, icon: Globe },
    { label: "Dipartimenti", value: stats.departments, icon: Building2 },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="flex items-center gap-4">
            <item.icon className="h-8 w-8 text-accent" />
            <div>
              <p className="text-2xl font-bold">{item.value}</p>
              <p className="text-sm text-muted-foreground">{item.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

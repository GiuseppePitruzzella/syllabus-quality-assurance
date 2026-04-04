import { Progress } from "@/components/ui/progress";

interface ScrapeProgressProps {
  current: number;
  total: number;
  message: string;
}

export function ScrapeProgress({
  current,
  total,
  message,
}: ScrapeProgressProps) {
  const percent = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className="space-y-2 py-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground truncate max-w-md">
          {message}
        </span>
        <span className="text-muted-foreground ml-2 shrink-0">
          {current}/{total}
        </span>
      </div>
      <Progress value={percent} />
    </div>
  );
}

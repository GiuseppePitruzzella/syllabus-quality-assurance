import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface EmptyStateProps {
  message: string;
  buttonLabel: string;
  onAction: () => void;
  disabled?: boolean;
}

export function EmptyState({
  message,
  buttonLabel,
  onAction,
  disabled,
}: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center gap-4 rounded-lg border border-dashed px-4 py-3">
      <p className="text-muted-foreground text-sm">{message}</p>
      <Button onClick={onAction} disabled={disabled}>
        <Download className="mr-2 h-4 w-4" />
        {buttonLabel}
      </Button>
    </div>
  );
}

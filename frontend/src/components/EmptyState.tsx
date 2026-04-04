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
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
      <p className="text-muted-foreground mb-4">{message}</p>
      <Button onClick={onAction} disabled={disabled}>
        <Download className="mr-2 h-4 w-4" />
        {buttonLabel}
      </Button>
    </div>
  );
}

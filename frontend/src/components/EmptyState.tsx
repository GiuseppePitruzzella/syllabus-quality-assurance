import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface EmptyStateProps {
  message: string;
  buttonLabel: string;
  onAction: () => void;
  disabled?: boolean;
}

/**
 * Phase 6.1.J — empty state shaped like a Select trigger.
 *
 * Used inline where a Select would normally sit (no Department,
 * no CdL, no syllabi yet) so the two halves of "Selezione corso"
 * stay the same height / shape even when one side has data and
 * the other is empty. Height (h-12), radius (rounded-xl), surface
 * (`bg-card shadow-xs`) and padding all match the new selector
 * triggers from 6.1.G.
 */
export function EmptyState({
  message,
  buttonLabel,
  onAction,
  disabled,
}: EmptyStateProps) {
  return (
    <div className="flex h-12 w-full items-center justify-between gap-3 rounded-xl border bg-card px-4 shadow-xs">
      <p className="truncate text-sm text-muted-foreground">{message}</p>
      <Button size="sm" onClick={onAction} disabled={disabled}>
        <Download aria-hidden />
        {buttonLabel}
      </Button>
    </div>
  );
}

import type { ReactNode } from "react";

interface ToolbarProps {
  /** Left-aligned slot — typically search inputs / filters. */
  children?: ReactNode;
  /** Right-aligned slot — typically primary / secondary actions. */
  actions?: ReactNode;
  /**
   * When true the toolbar renders without bottom margin so the caller
   * can stack it directly above a table. Default `true` so the
   * out-of-the-box layout has room for a single section body.
   */
  spaced?: boolean;
}

/**
 * Phase 6.0.A — horizontal toolbar above tables / lists.
 *
 * Replaces the inline `<div className="flex flex-wrap items-center
 * justify-between gap-3 ...">` pattern that 5.9.A introduced inside
 * the SyllabiTable header. Two slots: ``children`` for filters
 * (search input, status filter, ...) and ``actions`` for buttons
 * (Refresh, Export, ...). Wraps to two rows on narrow viewports.
 */
export function Toolbar({ children, actions, spaced = true }: ToolbarProps) {
  return (
    <div
      className={
        "flex flex-wrap items-center justify-between gap-3" +
        (spaced ? " mb-3" : "")
      }
    >
      <div className="flex flex-wrap items-center gap-2">{children}</div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}

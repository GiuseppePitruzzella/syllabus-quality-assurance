import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

export type BadgeTone = "cyan" | "emerald" | "amber" | "rose" | "neutral";

interface PageHeaderProps {
  /** Small uppercase tag above the title (e.g. "Valutazione", "Syllabus"). */
  badge?: string;
  badgeTone?: BadgeTone;
  title: ReactNode;
  /** Single-line context (e.g. teacher · CdL · year). */
  subtitle?: ReactNode;
  /**
   * Inline row directly under the subtitle for status pills, badges,
   * "anno N", language pill, etc. Rendered with a flex-wrap container
   * so it collapses gracefully on narrow viewports.
   */
  pills?: ReactNode;
  /**
   * Right-cluster slot for primary actions and toggles. On narrow
   * viewports it wraps under the title block.
   */
  actions?: ReactNode;
  /** Optional below-everything slot for advanced metadata / details. */
  footer?: ReactNode;
}

const badgeToneClass: Record<BadgeTone, string> = {
  cyan: "border-cyan-200 bg-cyan-500/10 text-cyan-800",
  emerald: "border-emerald-200 bg-emerald-500/10 text-emerald-800",
  amber: "border-amber-200 bg-amber-500/10 text-amber-800",
  rose: "border-rose-200 bg-rose-500/10 text-rose-800",
  neutral: "border-border bg-card text-foreground",
};

/**
 * Phase 6.0.A — page-level SaaS header.
 *
 * Replaces the inline header pattern that 5.9.A/B/C duplicated across
 * Dashboard / SyllabusViewer / EvaluationPage. The component is
 * intentionally presentation-only: it takes `title` / `subtitle` /
 * `pills` / `actions` as ReactNode so each page can compose its own
 * status pills and CTAs without forking the layout.
 */
export function PageHeader({
  badge,
  badgeTone = "cyan",
  title,
  subtitle,
  pills,
  actions,
  footer,
}: PageHeaderProps) {
  return (
    <header className="space-y-3 border-b pb-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          {badge ? (
            <Badge variant="outline" className={badgeToneClass[badgeTone]}>
              {badge}
            </Badge>
          ) : null}
          <h1 className="mt-3 text-3xl font-semibold tracking-normal leading-tight md:text-4xl">
            {title}
          </h1>
          {subtitle ? (
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              {subtitle}
            </p>
          ) : null}
          {pills ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">{pills}</div>
          ) : null}
        </div>
        {actions ? (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </div>
      {footer ? <div>{footer}</div> : null}
    </header>
  );
}

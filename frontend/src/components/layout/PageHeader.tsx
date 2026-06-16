import type { ReactNode } from "react";

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
  cyan: "text-sky-700",
  emerald: "text-emerald-700",
  amber: "text-amber-700",
  rose: "text-rose-700",
  neutral: "text-slate-500",
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
    <header className="space-y-5 pb-2">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          {badge ? (
            <p
              className={
                "text-[10px] font-semibold uppercase tracking-[0.16em] " +
                badgeToneClass[badgeTone]
              }
            >
              {badge}
            </p>
          ) : null}
          <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-normal text-slate-950 md:text-5xl">
            {title}
          </h1>
          {subtitle ? (
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-600">
              {subtitle}
            </p>
          ) : null}
          {pills ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">{pills}</div>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {footer ? <div>{footer}</div> : null}
    </header>
  );
}

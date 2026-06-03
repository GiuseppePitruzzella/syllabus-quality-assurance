import type { ReactNode } from "react";

interface SectionProps {
  title?: ReactNode;
  /** Right-side slot of the header bar (count chip, tab strip, toggle). */
  headerAside?: ReactNode;
  /** Optional one-line description under the title. */
  description?: ReactNode;
  /**
   * When true the body is rendered without padding so the consumer
   * can put a flush table / list inside. Default `true` (= p-4 body).
   */
  padded?: boolean;
  /** Pass through extra classes to the outer ``<section>``. */
  className?: string;
  children: ReactNode;
}

/**
 * Phase 6.0.A — content section with optional bordered header.
 *
 * Replaces the inline ``rounded-lg border bg-card`` + ``border-b
 * header`` pattern duplicated across Dashboard / SyllabusViewer /
 * EvaluationPage / EvaluationOutputTabs.
 *
 * When ``title`` (or ``headerAside``) is omitted the header bar is
 * not rendered at all, so the component degrades to a plain
 * card-shaped container.
 */
export function Section({
  title,
  headerAside,
  description,
  padded = true,
  className,
  children,
}: SectionProps) {
  const hasHeader = title !== undefined || headerAside !== undefined;
  const outerCls =
    "rounded-lg border bg-card" + (className ? ` ${className}` : "");
  return (
    <section className={outerCls}>
      {hasHeader ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
          {title ? (
            <div className="min-w-0">
              <h2 className="text-base font-semibold tracking-normal">
                {title}
              </h2>
              {description ? (
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {description}
                </p>
              ) : null}
            </div>
          ) : (
            <div />
          )}
          {headerAside ? <div>{headerAside}</div> : null}
        </div>
      ) : null}
      <div className={padded ? "p-4" : ""}>{children}</div>
    </section>
  );
}

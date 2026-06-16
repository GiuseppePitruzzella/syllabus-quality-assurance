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
 * Phase 10.A — content section with optional editorial header.
 *
 * Originally this replaced the inline ``rounded-lg border bg-card``
 * pattern duplicated across pages. The app now uses a document-like
 * layout: sections are separated by rhythm and, when siblings are
 * stacked, by the parent context — not by card boxes.
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
  const outerCls = "py-5 first:pt-0" + (className ? ` ${className}` : "");
  return (
    <section className={outerCls}>
      {hasHeader ? (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          {title ? (
            <div className="min-w-0">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                {title}
              </h2>
              {description ? (
                <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted-foreground">
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
      <div className={padded ? "" : ""}>{children}</div>
    </section>
  );
}

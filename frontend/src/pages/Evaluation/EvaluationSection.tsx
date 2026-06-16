import type { ReactNode } from "react";

/**
 * Phase 10.A R2 — lightweight section for the de-carded EvaluationPage.
 *
 * A heading row + content, with no card/border box. Siblings are
 * separated by a thin neutral rule applied by the parent (`divide-y`).
 * Replaces the `rounded-lg border bg-card` Section on this page.
 */
export function EvaluationSection({
  title,
  aside,
  children,
  className,
}: {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={"py-5 first:pt-0 " + (className ?? "")}>
      {title || aside ? (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title ? (
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              {title}
            </h2>
          ) : (
            <span />
          )}
          {aside ? <div>{aside}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

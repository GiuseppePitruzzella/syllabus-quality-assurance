/** Lightweight cross-component signal: the verdict banner asks the
 *  C1-C9 panel to expand specific criteria and scrolls to it. Sibling
 *  components, one-off interaction — a scoped window CustomEvent keeps
 *  them decoupled without lifting state through the page. */

export const CRITERIA_SECTION_ID = "criteri-core";
export const FOCUS_CRITERIA_EVENT = "sqa:focus-criteria";

export interface FocusCriteriaDetail {
  codes: string[];
}

/** Expand the given criteria (if any) and scroll the C1-C9 panel into view. */
export function focusCriteria(codes: string[]): void {
  if (codes.length > 0) {
    window.dispatchEvent(
      new CustomEvent<FocusCriteriaDetail>(FOCUS_CRITERIA_EVENT, {
        detail: { codes },
      }),
    );
  }
  document
    .getElementById(CRITERIA_SECTION_ID)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

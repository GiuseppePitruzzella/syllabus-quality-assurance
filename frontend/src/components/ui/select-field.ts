/**
 * Shared visual styling for the app's borderless "underline" select fields:
 * the Dashboard department/CdL pickers and the Results CdS export combo.
 *
 * Sizing (height/width) is intentionally NOT included — each call site
 * composes these with its own dimensions via `cn`, so a full-width form
 * field and a compact header action stay visually consistent.
 */
export const selectFieldTrigger =
  "justify-start rounded-none border-x-0 border-t-0 border-b border-slate-300 bg-transparent px-0 text-sm font-medium text-slate-950 shadow-none transition-colors hover:border-slate-500 hover:bg-transparent focus-visible:border-slate-950 focus-visible:ring-0 data-[popup-open]:border-slate-950 data-[popup-open]:ring-0 disabled:bg-transparent disabled:text-slate-400 data-placeholder:text-sm data-placeholder:font-normal [&_svg]:size-4";

export const selectFieldContent = "rounded-none shadow-lg ring-1 ring-slate-200";

export const selectFieldItem =
  "rounded-none px-2 py-2 focus:bg-slate-100 focus:text-slate-950";

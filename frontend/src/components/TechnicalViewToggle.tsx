import { useTechnicalView } from "@/context/technicalView";

/** Accessible switch controlling the global Technical View, with a
 *  contextual caption explaining the two views. Sits in the dark
 *  navbar next to the profile mock. */
export function TechnicalViewToggle() {
  const { technical, toggle } = useTechnicalView();
  return (
    <div className="flex flex-col items-end">
      <button
        type="button"
        role="switch"
        aria-checked={technical}
        aria-label="Vista tecnica"
        title="Guidata: lettura per la revisione · Tecnica: esecuzione, agenti, RAG"
        onClick={toggle}
        className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-slate-300 transition-colors hover:text-white"
      >
        <span
          aria-hidden
          className={
            "relative inline-flex h-4 w-7 items-center rounded-full transition-colors " +
            (technical ? "bg-emerald-500" : "bg-slate-600")
          }
        >
          <span
            className={
              "inline-block h-3 w-3 rounded-full bg-white transition-transform " +
              (technical ? "translate-x-3.5" : "translate-x-0.5")
            }
          />
        </span>
        <span className="hidden sm:inline">Vista tecnica</span>
      </button>
      <span className="hidden pr-2.5 text-[9px] leading-tight text-slate-500 lg:block">
        {technical
          ? "Tecnica: esecuzione, agenti, RAG"
          : "Guidata: lettura per la revisione"}
      </span>
    </div>
  );
}

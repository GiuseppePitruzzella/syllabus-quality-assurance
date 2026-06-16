import type { ReactNode } from "react";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="grid min-h-screen lg:grid-cols-[minmax(0,0.95fr)_minmax(380px,0.55fr)]">
        <section className="hidden border-r border-slate-200 bg-slate-950 px-10 py-10 text-white lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold tracking-wide">
              <span className="inline-block h-2 w-2 rounded-sm bg-emerald-400" />
              Syllabus Quality Assurance
            </div>
            <div className="mt-28 max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
                Tesi di Laurea Magistrale · LM-18 UNICT
              </p>
              <h1 className="mt-6 text-6xl font-semibold leading-[0.95] tracking-tight">
                Accesso alla piattaforma di valutazione dei syllabus.
              </h1>
              <p className="mt-8 max-w-2xl text-lg leading-8 text-slate-300">
                Analisi multi-agentica, criteri C1-C9, documenti esterni e
                report leggibili in un unico ambiente controllato.
              </p>
            </div>
          </div>
          <div className="grid max-w-3xl grid-cols-3 gap-8 border-t border-white/10 pt-8 text-sm text-slate-300">
            <div>
              <p className="text-2xl font-semibold text-white">C1-C9</p>
              <p className="mt-2">Rubrica core e CoreScore separati dai criteri estesi.</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-white">A1-A5</p>
              <p className="mt-2">Agenti specialistici con tracciabilità di prompt e fonti.</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-white">E1-E5</p>
              <p className="mt-2">Governance documentale e criteri estesi fuori dal CoreScore.</p>
            </div>
          </div>
        </section>
        <section className="flex items-center justify-center px-5 py-10 sm:px-8">
          <div className="w-full max-w-md">{children}</div>
        </section>
      </div>
    </div>
  );
}

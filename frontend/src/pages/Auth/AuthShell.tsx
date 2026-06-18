import type { ReactNode } from "react";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="grid min-h-screen lg:grid-cols-[minmax(0,0.95fr)_minmax(380px,0.55fr)]">
        <section className="hidden border-r border-slate-200 bg-white px-10 py-10 text-slate-950 lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold tracking-wide">
              <span className="inline-block h-2 w-2 rounded-sm bg-cyan-500" />
              Syllabus Quality Assurance
            </div>
            <div className="mt-28 max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700">
                Tesi di Laurea Magistrale · LM-18 UNICT · A.A. 2025/2026
              </p>
              <h1 className="mt-6 text-6xl font-semibold leading-[0.95] tracking-tight">
                Architettura Multi-Agente per la Quality Assurance nei Syllabus
                Universitari.
              </h1>
              <p className="mt-8 max-w-2xl text-lg leading-8 text-slate-600">
                Una piattaforma utile alla revisione qualitativa di tutti i
                corsi dell&apos;Università Degli Studi di Catania, attraverso:
                criteri, agenti e riferimenti a documenti normativi.
              </p>
            </div>
          </div>
          <div className="grid max-w-3xl grid-cols-3 gap-8 border-t border-slate-200 pt-8 text-sm text-slate-600">
            <div>
              <p className="text-2xl font-semibold text-cyan-700">C1-C9</p>
              <p className="mt-2">Rubrica core per leggere completezza, coerenza e cura.</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-cyan-700">A1-A5</p>
              <p className="mt-2">Agenti specialistici con prompt, evidenze e versioni tracciate.</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-cyan-700">E1-E5</p>
              <p className="mt-2">Criteri estesi collegati ai documenti locali e istituzionali.</p>
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

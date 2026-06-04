import { useState } from "react";
import { ChevronRight, FileText, FlaskConical } from "lucide-react";

import { Section } from "@/components/layout/Section";
import {
  CORE_CRITERIA,
  EXTENDED_CRITERIA,
  type CoreCriterion,
  type ExtendedCriterion,
  type Score,
} from "@/data/rubric";

/**
 * Phase 7 — Rubrica.
 *
 * Due blocchi nettamente separati:
 *
 *   1. Criteri core C1-C9 — tabella expand-on-click. Ogni riga
 *      mostra codice, area, agente, peso, versione prompt. Cliccando
 *      la riga si espandono descrizione, anchors 0/1/2/NA e note.
 *
 *   2. Criteri estesi E1-E5 — blocco visivamente distinto, sfondo
 *      tono caldo (amber), banner esplicito "Non concorrono al
 *      CoreScore". Niente expand: ogni criterio è una card piatta
 *      con descrizione, prerequisito documentale e status.
 *
 * La separazione è metodologica: il lettore non deve mai poter
 * confondere E1-E5 col nucleo della validazione principale.
 */
export function RubricSection() {
  return (
    <>
      <Section
        title="Criteri core C1-C9"
        description="Concorrono al CoreScore. Scala ordinale 0/1/2 con NA riservato alla non-valutabilità tecnica."
        padded={false}
      >
        <CoreRubricTable />
      </Section>

      <Section
        title="Criteri estesi E1-E5"
        description="Sperimentali / futuri. Richiedono documenti aggiuntivi non uniformemente disponibili."
        headerAside={
          <span className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-800">
            <FlaskConical className="h-3 w-3" aria-hidden />
            Non concorrono al CoreScore
          </span>
        }
      >
        <p className="mb-4 rounded-md border border-dashed border-amber-300 bg-amber-500/[0.06] px-3 py-2 text-xs leading-relaxed text-amber-900/90">
          I criteri estesi sono mantenuti separati dal nucleo C1-C9 per
          preservare la simmetria informativa tra sistema automatico e
          valutatori umani: entrambi giudicano dallo stesso perimetro
          (il testo del syllabus). Gli E sono attivabili solo quando il
          documento esterno richiesto è disponibile e la run lo segnala
          esplicitamente.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {EXTENDED_CRITERIA.map((c) => (
            <ExtendedCard key={c.code} criterion={c} />
          ))}
        </div>
      </Section>
    </>
  );
}

// ---------------------------------------------------------------------------
// Core table
// ---------------------------------------------------------------------------

function CoreRubricTable() {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (code: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });

  return (
    <div className="overflow-hidden rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="w-8 px-2 py-2" aria-hidden />
            <th className="w-14 px-3 py-2 text-left font-medium">Cod.</th>
            <th className="px-3 py-2 text-left font-medium">Criterio</th>
            <th className="w-32 px-3 py-2 text-left font-medium">Area</th>
            <th className="w-16 px-3 py-2 text-left font-medium">Agente</th>
            <th className="w-14 px-3 py-2 text-right font-medium">Peso</th>
            <th className="w-24 px-3 py-2 text-left font-medium">Prompt</th>
          </tr>
        </thead>
        <tbody>
          {CORE_CRITERIA.map((c) => (
            <CoreRow
              key={c.code}
              criterion={c}
              expanded={expanded.has(c.code)}
              onToggle={() => toggle(c.code)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CoreRow({
  criterion: c,
  expanded,
  onToggle,
}: {
  criterion: CoreCriterion;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="cursor-pointer border-t transition-colors hover:bg-muted/30"
        onClick={onToggle}
      >
        <td className="px-2 py-2 text-muted-foreground">
          <ChevronRight
            className={
              "h-4 w-4 transition-transform " + (expanded ? "rotate-90" : "")
            }
            aria-hidden
          />
        </td>
        <td className="px-3 py-2 font-mono text-xs">{c.code}</td>
        <td className="px-3 py-2">{c.name}</td>
        <td className="px-3 py-2 text-xs text-muted-foreground">{c.area}</td>
        <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
          {c.agent}
        </td>
        <td className="px-3 py-2 text-right tabular-nums">
          {c.weight.toFixed(1)}
        </td>
        <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
          {c.prompt_version}
        </td>
      </tr>
      {expanded ? (
        <tr className="border-t bg-muted/20">
          <td colSpan={7} className="px-6 py-4">
            <CoreDetails criterion={c} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function CoreDetails({ criterion: c }: { criterion: CoreCriterion }) {
  return (
    <div className="space-y-4">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Descrizione
        </p>
        <p className="text-sm leading-relaxed">{c.description}</p>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Anchors
        </p>
        <ul className="space-y-1.5">
          {c.anchors.map((a) => (
            <li key={String(a.score)} className="flex items-start gap-3">
              <ScoreBadge score={a.score} />
              <span className="text-sm leading-relaxed text-foreground/90">
                {a.description}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {c.notes ? (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Note metodologiche
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {c.notes}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function ScoreBadge({ score }: { score: Score }) {
  let cls =
    "inline-flex h-6 w-9 shrink-0 items-center justify-center rounded-md border text-xs font-medium tabular-nums";
  let label: string;
  if (score === 2) {
    cls += " border-emerald-300 bg-emerald-500/10 text-emerald-800";
    label = "2";
  } else if (score === 1) {
    cls += " border-amber-300 bg-amber-500/10 text-amber-800";
    label = "1";
  } else if (score === 0) {
    cls += " border-rose-300 bg-rose-500/10 text-rose-800";
    label = "0";
  } else {
    cls += " border-border bg-muted text-muted-foreground";
    label = "NA";
  }
  return <span className={cls}>{label}</span>;
}

// ---------------------------------------------------------------------------
// Extended cards
// ---------------------------------------------------------------------------

function ExtendedCard({ criterion: c }: { criterion: ExtendedCriterion }) {
  return (
    <div className="rounded-md border border-amber-200 bg-amber-500/[0.04] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <code className="rounded bg-amber-500/10 px-1.5 py-0.5 font-mono text-xs font-semibold text-amber-900">
          {c.code}
        </code>
        <h4 className="text-sm font-medium text-foreground">{c.name}</h4>
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          {c.local_document ? (
            <span className="inline-flex items-center gap-1 rounded-md border border-cyan-300 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-cyan-800">
              <FileText className="h-3 w-3" aria-hidden />
              Richiede documento locale
            </span>
          ) : null}
          <span className="rounded-md border border-amber-300 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-800">
            {c.status}
          </span>
        </div>
      </div>

      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        {c.description}
      </p>

      <dl className="mt-3 space-y-1.5 text-xs">
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 font-medium text-muted-foreground">
            Area
          </dt>
          <dd className="text-foreground/90">{c.area}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 font-medium text-muted-foreground">
            Agente
          </dt>
          <dd className="font-mono text-foreground/90">{c.agent}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 font-medium text-muted-foreground">
            Richiede
          </dt>
          <dd className="text-foreground/90">{c.requires}</dd>
        </div>
      </dl>

      {c.anchors ? (
        <div className="mt-3">
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Anchors
          </p>
          <ul className="space-y-1.5">
            {c.anchors.map((a) => (
              <li key={String(a.score)} className="flex items-start gap-2">
                <ScoreBadge score={a.score} />
                <span className="text-xs leading-relaxed text-foreground/90">
                  {a.description}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {c.notes && c.notes.length > 0 ? (
        <div className="mt-3">
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Note metodologiche
          </p>
          <ul className="space-y-1 text-xs leading-relaxed text-muted-foreground">
            {c.notes.map((n, i) => (
              <li key={i} className="flex gap-2">
                <span
                  aria-hidden
                  className="mt-1.5 inline-block h-1 w-1 shrink-0 rounded-full bg-muted-foreground/60"
                />
                <span>{n}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}


import { Section } from "@/components/layout/Section";
import { HUMAN_VALIDATION_PROTOCOL } from "@/data/validation";

/**
 * Phase 7 — Validazione umana (Phase 5.8).
 *
 * Espone il protocollo di validazione uomo-macchina come scheda
 * informativa. Nessun fetch ai CSV: la shortlist e le metriche
 * sono costanti statiche derivate dagli artefatti in
 * `data/human_judgment/` e dallo script aggregator.
 */
export function ValidationSection() {
  const p = HUMAN_VALIDATION_PROTOCOL;

  return (
    <Section
      title="Protocollo di validazione umana"
      description={p.phase}
    >
      <div className="space-y-5">
        <Block label="Dataset di partenza">
          <p className="text-sm leading-relaxed text-foreground/90">
            {p.total_dataset}
          </p>
        </Block>

        <Block label="Shortlist (8 syllabi)">
          <ol className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {p.shortlist.map((it) => (
              <li
                key={it.ordinal}
                className="flex items-center gap-3 rounded-md border bg-card px-3 py-1.5 text-sm"
              >
                <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border bg-muted text-[10px] font-medium tabular-nums text-muted-foreground">
                  {it.ordinal}
                </span>
                <span className="truncate text-foreground/90">
                  {it.syllabus}
                </span>
              </li>
            ))}
          </ol>
        </Block>

        <Block label="Modalità">
          <ul className="space-y-1.5 text-sm leading-relaxed">
            {p.modes.map((m, i) => (
              <li key={i} className="flex gap-2">
                <span
                  aria-hidden
                  className="mt-2 inline-block h-1 w-1 shrink-0 rounded-full bg-muted-foreground/60"
                />
                <span className="text-foreground/90">{m}</span>
              </li>
            ))}
          </ul>
        </Block>

        <Block label="Metriche">
          <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {p.metrics.map((m) => (
              <div
                key={m.name}
                className="rounded-md border bg-card px-3 py-2"
              >
                <dt className="text-sm font-medium text-foreground">
                  {m.name}
                </dt>
                <dd className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                  {m.description}
                </dd>
              </div>
            ))}
          </dl>
        </Block>

        <Block label="Artefatti">
          <ul className="space-y-1 font-mono text-xs text-muted-foreground">
            <li>
              templates · <span className="text-foreground/90">{p.templates_path}</span>
            </li>
            <li>
              schema · <span className="text-foreground/90">{p.schema_path}</span>
            </li>
            <li>
              aggregator · <span className="text-foreground/90">{p.aggregator_script}</span>
            </li>
          </ul>
        </Block>
      </div>
    </Section>
  );
}

function Block({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}

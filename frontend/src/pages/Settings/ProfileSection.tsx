import { Lock } from "lucide-react";

import { Section } from "@/components/layout/Section";
import { ACTIVE_PROFILE } from "@/data/profile";

/**
 * Phase 7 — Profilo di valutazione (read-only).
 *
 * Mostra i parametri del profilo attivo come una scheda di
 * versionamento, non come un form. Un badge "Bloccato per
 * riproducibilità" rende esplicito il vincolo: una modifica deve
 * generare una nuova versione del profilo.
 */
export function ProfileSection() {
  const p = ACTIVE_PROFILE;

  return (
    <Section
      title="Profilo di valutazione"
      description="Snapshot dei parametri scientifici della run attiva. Sincronizzato a mano col backend per ragioni di riproducibilità."
      headerAside={
        p.locked ? (
          <span className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-800">
            <Lock className="h-3 w-3" aria-hidden />
            Bloccato per riproducibilità
          </span>
        ) : null
      }
    >
      <dl className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
        <Field label="Nome profilo" value={p.name} />
        <Field label="Rubrica" value={p.rubric_label} />
        <Field label="Modello LLM" value={p.llm_model} mono />
        <Field label="Modello embedding" value={p.embedding_model} mono />
        <Field label="Versioni prompt">
          <ul className="flex flex-wrap gap-1.5">
            {p.prompt_versions.map((pv) => (
              <li key={pv.agent}>
                <span className="inline-flex items-center gap-1 rounded-md border bg-card px-2 py-0.5 font-mono text-xs text-foreground">
                  <span className="text-muted-foreground">{pv.agent}</span>
                  <span aria-hidden className="text-muted-foreground">/</span>
                  {pv.version}
                </span>
              </li>
            ))}
          </ul>
        </Field>
        <Field
          label="Parametri LLM"
          value={`temp ${p.llm_temperature} · max_output ${p.llm_max_output_tokens} (A1 override ${p.llm_a1_max_output_tokens_override})`}
          mono
        />
        <Field
          label="Retrieval RAG"
          value={`top_k ${p.rag_top_k} · soglia ${p.rag_similarity_threshold}`}
          mono
        />
        <Field
          label="Embedding dim."
          value={String(p.embedding_output_dimensionality)}
          mono
        />
        <Field label="Location GCP" value={p.gcp_location} mono />
      </dl>

      {p.locked ? (
        <p className="mt-5 rounded-md border border-dashed bg-muted/40 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          {p.locked_reason}
        </p>
      ) : null}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Local field row — keeps the layout consistent without pulling in a new primitive.
// ---------------------------------------------------------------------------

function Field({
  label,
  value,
  mono,
  children,
}: {
  label: string;
  value?: string;
  mono?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        className={
          "mt-1 text-sm text-foreground " + (mono ? "font-mono" : "")
        }
      >
        {children ?? value ?? "—"}
      </dd>
    </div>
  );
}

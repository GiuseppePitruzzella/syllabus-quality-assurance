import { PageHeader } from "@/components/layout/PageHeader";

import { ProfileSection } from "./ProfileSection";
import { RubricSection } from "./RubricSection";
import { NormativeCorpusSection } from "./NormativeCorpusSection";
import { SourcesSection } from "./SourcesSection";

/**
 * Phase 7 — Impostazioni (MVP statico, read-only).
 *
 * La pagina non è un pannello di preferenze utente: è la vista di
 * governance scientifica del sistema. Espone profilo attivo, rubrica
 * e fonti documentali così come sono versionate nel repository.
 * Nessun editing: una modifica metodologica deve generare una nuova
 * versione del profilo per preservare la riproducibilità.
 *
 * Le sezioni vivono in un'unica pagina scroll-based:
 *   1. Profilo di valutazione — preset attivo, bloccato per
 *      riproducibilità.
 *   2. Rubrica — C1-C9 (core) chiaramente separati dai criteri
 *      estesi E1-E5 (sperimentali / futuri), con nota esplicita
 *      "Non concorrono al CoreScore".
 *   3. Corpus normativo CoreScore e fonti E1-E5.
 */
export function SettingsPage() {
  return (
    <div className="mx-auto w-full max-w-[1720px] space-y-10">
      <PageHeader
        badge="Governance"
        badgeTone="neutral"
        title="Impostazioni"
        subtitle="Profilo di valutazione, rubrica e fonti documentali del sistema. Le impostazioni sono read-only: una modifica deve generare una nuova versione del profilo per preservare la riproducibilità."
      />
      <ProfileSection />
      <RubricSection />
      <NormativeCorpusSection />
      <SourcesSection />
    </div>
  );
}

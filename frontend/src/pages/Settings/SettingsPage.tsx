import { PageHeader } from "@/components/layout/PageHeader";

import { ProfileSection } from "./ProfileSection";
import { RubricSection } from "./RubricSection";
import { SourcesSection } from "./SourcesSection";
import { ValidationSection } from "./ValidationSection";

/**
 * Phase 7 — Impostazioni (MVP statico, read-only).
 *
 * La pagina non è un pannello di preferenze utente: è la vista di
 * governance scientifica del sistema. Espone profilo attivo,
 * rubrica e protocollo di validazione umana così come sono
 * versionati nel repository. Nessun fetch, nessun editing, nessuna
 * lettura runtime di `docs/` o `data/`.
 *
 * Le tre sezioni vivono in un'unica pagina scroll-based:
 *   1. Profilo di valutazione — preset attivo, bloccato per
 *      riproducibilità.
 *   2. Rubrica — C1-C9 (core) chiaramente separati dai criteri
 *      estesi E1-E5 (sperimentali / futuri), con nota esplicita
 *      "Non concorrono al CoreScore".
 *   3. Validazione umana — protocollo Phase 5.8.
 */
export function SettingsPage() {
  return (
    <div className="mx-auto w-full max-w-[1720px] space-y-10">
      <PageHeader
        badge="Governance"
        badgeTone="neutral"
        title="Impostazioni"
        subtitle="Profilo di valutazione, rubrica e protocollo di validazione umana del sistema. Le impostazioni sono read-only: una modifica deve generare una nuova versione del profilo per preservare la riproducibilità."
      />
      <ProfileSection />
      <RubricSection />
      <SourcesSection />
      <ValidationSection />
    </div>
  );
}

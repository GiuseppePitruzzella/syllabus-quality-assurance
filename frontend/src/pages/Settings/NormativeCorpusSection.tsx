import { useQuery } from "@tanstack/react-query";

import {
  NormativeCorpusError,
  NormativeCorpusLoading,
  NormativeCorpusTable,
} from "@/components/NormativeCorpusTable";
import { Section } from "@/components/layout/Section";
import { listNormativeCorpusDocuments } from "@/lib/api";

export function NormativeCorpusSection() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["normative-corpus-documents"],
    queryFn: listNormativeCorpusDocuments,
  });

  return (
    <Section
      title="Corpus normativo CoreScore"
      description="Sette documenti versionati usati dal retriever normativo degli agenti A1-A4 per motivare i criteri C1-C9. È un corpus fisso di progetto, distinto dai documenti locali E1-E5."
      headerAside={
        data ? (
          <span className="bg-muted px-2 py-0.5 text-[11px] font-medium tabular-nums text-muted-foreground">
            {data.length}
          </span>
        ) : null
      }
    >
      {isError ? (
        <NormativeCorpusError
          message={error instanceof Error ? error.message : String(error)}
        />
      ) : isLoading || !data ? (
        <NormativeCorpusLoading />
      ) : (
        <div className="space-y-3">
          <NormativeCorpusTable documents={data} />
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            I tag C1-C9 indicano quali documenti possono essere recuperati dal
            RAG per ciascun criterio CoreScore. Il corpus attivo mostra solo
            fonti che alimentano almeno un criterio core.
          </p>
        </div>
      )}
    </Section>
  );
}

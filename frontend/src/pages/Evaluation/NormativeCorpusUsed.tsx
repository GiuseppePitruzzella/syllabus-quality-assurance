import { useQuery } from "@tanstack/react-query";

import {
  NormativeCorpusError,
  NormativeCorpusLoading,
  NormativeCorpusTable,
} from "@/components/NormativeCorpusTable";
import { listNormativeCorpusDocuments } from "@/lib/api";
import { EvaluationSection } from "./EvaluationSection";

export function NormativeCorpusUsed() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["normative-corpus-documents"],
    queryFn: listNormativeCorpusDocuments,
  });

  return (
    <EvaluationSection
      title="Corpus normativo CoreScore"
      aside={
        data ? (
          <span className="text-xs text-slate-500">
            {data.length} fonti attive · C1-C9
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
          <p className="text-[11px] leading-relaxed text-slate-500">
            Queste fonti alimentano il retriever normativo del CoreScore. A
            differenza dei documenti E1-E5, non sono selezionate per singola
            run: sono il corpus fisso e versionato degli agenti A1-A4.
          </p>
        </div>
      )}
    </EvaluationSection>
  );
}

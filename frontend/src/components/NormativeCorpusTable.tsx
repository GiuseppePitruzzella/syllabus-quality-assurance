import { Database, FileText } from "lucide-react";

import { useTechnicalView } from "@/context/technicalView";
import type { CoreAgentCode, CoreCriterionCode, NormativeCorpusDocument } from "@/lib/types";

interface Props {
  documents: NormativeCorpusDocument[];
}

export function NormativeCorpusTable({ documents }: Props) {
  const { technical } = useTechnicalView();

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-[10px] uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Documento</th>
            <th className="px-3 py-2 text-left font-medium">Tipo</th>
            <th className="px-3 py-2 text-left font-medium">Criteri Core</th>
            {technical ? (
              <th className="px-3 py-2 text-left font-medium">Agenti</th>
            ) : null}
            {technical ? (
              <th className="w-20 px-3 py-2 text-left font-medium">Chunk</th>
            ) : null}
            {technical ? (
              <th className="w-24 px-3 py-2 text-left font-medium">Hash</th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.document_id} className="border-t border-slate-200/80">
              <td className="px-3 py-2 align-top">
                <DocumentTitle doc={doc} />
              </td>
              <td className="px-3 py-2 align-top">
                <span className="text-xs text-slate-600">
                  {labelForSourceType(doc.source_type)}
                </span>
                {doc.version ? (
                  <div className="mt-0.5 font-mono text-[10px] text-slate-400">
                    {doc.version}
                  </div>
                ) : null}
              </td>
              <td className="px-3 py-2 align-top">
                <CriterionPills criteria={doc.core_criteria} />
              </td>
              {technical ? (
                <td className="px-3 py-2 align-top">
                  <AgentPills agents={doc.agents} />
                </td>
              ) : null}
              {technical ? (
                <td className="px-3 py-2 align-top font-mono text-xs tabular-nums text-slate-600">
                  {doc.core_chunk_count}/{doc.chunk_count}
                </td>
              ) : null}
              {technical ? (
                <td className="px-3 py-2 align-top">
                  <code
                    className="bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500"
                    title={`${doc.filename} · ${doc.file_hash}`}
                  >
                    {shortHash(doc.file_hash)}
                  </code>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DocumentTitle({ doc }: { doc: NormativeCorpusDocument }) {
  return (
    <div className="min-w-64">
      <div className="flex items-start gap-2">
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden />
        <div>
          <h3 className="text-sm font-medium text-slate-950">{doc.title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
            <code className="font-mono">{doc.document_id}</code>
            {!doc.is_core_source ? (
              <span className="bg-slate-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
                contesto
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function CriterionPills({ criteria }: { criteria: CoreCriterionCode[] }) {
  if (criteria.length === 0) {
    return <span className="text-xs text-slate-500">Nessun tag C1-C9 diretto</span>;
  }
  return (
    <span className="flex flex-wrap gap-1">
      {criteria.map((criterion) => (
        <code
          key={criterion}
          className="bg-sky-500/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-sky-900"
        >
          {criterion}
        </code>
      ))}
    </span>
  );
}

function AgentPills({ agents }: { agents: CoreAgentCode[] }) {
  if (agents.length === 0) {
    return <span className="text-xs text-slate-500">—</span>;
  }
  return (
    <span className="flex flex-wrap gap-1">
      {agents.map((agent) => (
        <code
          key={agent}
          className="bg-slate-500/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-slate-700"
        >
          {agent}
        </code>
      ))}
    </span>
  );
}

function labelForSourceType(sourceType: string): string {
  const labels: Record<string, string> = {
    linea_guida_ateneo: "Linea guida di Ateneo",
    linea_guida_anvur: "Linea guida ANVUR",
    normativa_ministeriale: "Normativa ministeriale",
  };
  return labels[sourceType] ?? sourceType.replace(/_/g, " ");
}

function shortHash(hash: string): string {
  return hash.length > 7 ? hash.slice(0, 7) : hash;
}

export function NormativeCorpusLoading() {
  return (
    <div className="space-y-2" aria-busy>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="h-14 animate-pulse bg-slate-100" />
      ))}
    </div>
  );
}

export function NormativeCorpusError({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 bg-rose-500/10 px-3 py-2 text-sm text-rose-900">
      <Database className="h-4 w-4" aria-hidden />
      Impossibile caricare il corpus normativo.{" "}
      <span className="text-xs text-rose-800/80">{message}</span>
    </div>
  );
}

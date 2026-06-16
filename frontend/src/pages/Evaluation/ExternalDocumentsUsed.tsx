import { Archive, FileText } from "lucide-react";

import { ResolutionReasonPill } from "@/components/ResolutionReasonPill";
import { useTechnicalView } from "@/context/technicalView";
import type { EvaluationDetail } from "@/lib/types";
import { EvaluationSection } from "./EvaluationSection";

interface Props {
  data: EvaluationDetail;
}

/**
 * Phase 9.D.3 — Read-only audit view of which registry documents
 * fed which extended criterion in this run.
 *
 * The component only renders when ``external_documents_used`` is
 * non-empty. The user's contract (9.D.3) makes that explicit: an
 * empty list should be invisible, not a "no data" pane, so the
 * core flow stays uncluttered for runs that didn't consume
 * documents (which is the common case for LM-18 today).
 *
 * Snapshot fields (criterion, type, version, file_hash,
 * resolution_reason) are the *primary* source of truth — they were
 * captured at run time and are what makes the run reproducible
 * even if the registry has since changed. The live ``title`` and
 * the ``deleted_at`` flag come from the LocalDocument row and are
 * shown as accessory information: the title makes the row
 * human-readable, and the archived pill flags when a referenced
 * document has been soft-deleted (Phase 9.B.3) so the historical
 * run remains interpretable.
 *
 * No link to a "document detail" page is rendered: there is no
 * such endpoint today. Adding one is out of scope for 9.D.
 */
export function ExternalDocumentsUsed({ data }: Props) {
  const { technical } = useTechnicalView();
  const docs = data.external_documents_used;
  if (!docs || docs.length === 0) return null;

  return (
    <EvaluationSection
      title="Documenti utilizzati"
      aside={
        <span className="text-xs text-muted-foreground">
          {docs.length} {docs.length === 1 ? "documento" : "documenti"} ·
          {" "}snapshot al momento della run
        </span>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-[10px] uppercase tracking-wide text-slate-400">
            <tr>
              <th className="w-14 px-3 py-2 text-left font-medium">Crit</th>
              <th className="px-3 py-2 text-left font-medium">Tipo</th>
              {technical ? (
                <th className="w-14 px-3 py-2 text-left font-medium">Ver</th>
              ) : null}
              {technical ? (
                <th className="w-24 px-3 py-2 text-left font-medium">Hash</th>
              ) : null}
              <th className="w-40 px-3 py-2 text-left font-medium">
                Resolution
              </th>
              <th className="px-3 py-2 text-left font-medium">Titolo</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc, i) => (
              <tr
                key={`${doc.criterion_code}-${doc.local_document_id}-${i}`}
                className="border-t border-slate-200/80"
              >
                <td className="px-3 py-2 font-mono text-xs">
                  {doc.criterion_code}
                </td>
                <td className="px-3 py-2">
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {doc.document_type}
                  </span>
                </td>
                {technical ? (
                  <td className="px-3 py-2 font-mono text-xs tabular-nums">
                    v{doc.document_version}
                  </td>
                ) : null}
                {technical ? (
                  <td className="px-3 py-2">
                    <code
                      className="bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                      title={doc.file_hash}
                    >
                      {shortHash(doc.file_hash)}
                    </code>
                  </td>
                ) : null}
                <td className="px-3 py-2 text-xs">
                  <ResolutionReasonPill reason={doc.resolution_reason} />
                </td>
                <td className="px-3 py-2">
                  <DocumentTitleCell
                    title={doc.title}
                    deletedAt={doc.deleted_at}
                    docId={doc.local_document_id}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {technical ? (
        <p className="mt-3 text-[11px] text-muted-foreground">
          Le colonne tipo / versione / hash riportano lo snapshot dell'audit:
          rappresentano lo stato del documento al momento della run e
          restano stabili anche se il documento viene successivamente
          modificato o archiviato. Il titolo è invece letto dal registry
          attuale.
        </p>
      ) : null}
    </EvaluationSection>
  );
}

// ---------------------------------------------------------------------------
// Cells
// ---------------------------------------------------------------------------

function DocumentTitleCell({
  title,
  deletedAt,
  docId,
}: {
  title: string | null;
  deletedAt: string | null;
  docId: number;
}) {
  // Title may be null only if the live row was hard-deleted, which
  // the FK RESTRICT normally prevents. Render the document id as a
  // last-resort label so the row remains identifiable.
  const label =
    title ?? <span className="text-muted-foreground">id={docId}</span>;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <FileText
        className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
        aria-hidden
      />
      <span className="text-sm">{label}</span>
      {deletedAt ? <ArchivedPill deletedAt={deletedAt} /> : null}
    </div>
  );
}

function ArchivedPill({ deletedAt }: { deletedAt: string }) {
  // Format the timestamp loosely — exact precision belongs in a
  // hover, not in the inline pill.
  const date = new Date(deletedAt);
  const label = Number.isNaN(date.getTime())
    ? "archiviato"
    : `archiviato il ${date.toLocaleDateString("it-IT", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })}`;
  return (
    <span
      className="inline-flex items-center gap-1 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300"
      title={`Soft-delete applicato: il documento è preservato perché referenziato da questa run. deleted_at = ${deletedAt}`}
    >
      <Archive className="h-3 w-3" aria-hidden />
      {label}
    </span>
  );
}

function shortHash(hash: string): string {
  // Mirror the convention used in the local-documents UI for
  // consistency: first 7 chars (git-like).
  return hash.length > 7 ? hash.slice(0, 7) : hash;
}

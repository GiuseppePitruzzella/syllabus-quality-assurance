import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { EvaluationDetail } from "@/lib/types";
import { useTechnicalView } from "@/context/technicalView";
import { EvaluationSection } from "./EvaluationSection";

interface Props {
  data: EvaluationDetail;
}

/**
 * Phase 10.A R1 — "Report di valutazione".
 *
 * Reduced from the former tabbed "Output valutazione": now a single
 * section containing only the readable Markdown report. The syllabus
 * split-view and the "Dettagli agenti" tab were removed — agent
 * inspection lives in the technical-only `AgentDetailsSection`, and
 * the original syllabus remains one click away via the header link.
 */
export function EvaluationReport({ data }: Props) {
  const { technical } = useTechnicalView();
  // A failed run's synthesized report embeds raw execution errors
  // (TransportError, hosts, traceback). In guided view it must be
  // replaced by a plain notice; the full report stays in technical.
  const redactRawReport = !technical && data.status === "failed";

  return (
    <EvaluationSection title="Report di valutazione" className="min-w-0">
      <div className="max-w-[78ch]">
        {redactRawReport ? (
          <p className="text-sm text-slate-600">
            Il report non è disponibile perché la valutazione non è stata
            completata. I dettagli di esecuzione sono disponibili agli account
            con ruolo tecnico o amministrativo.
          </p>
        ) : (
          <ReportPanel data={data} />
        )}
      </div>
    </EvaluationSection>
  );
}

function ReportPanel({ data }: { data: EvaluationDetail }) {
  if (!data.final_report) {
    return (
      <p className="text-sm text-slate-500">
        Il report sarà disponibile al termine della fase di sintesi
        (evento <code>report_synthesized</code>).
      </p>
    );
  }
  return <ReportMarkdown source={data.final_report} />;
}

/**
 * Sober QA-document styling: small headings, scrollable tables,
 * subtle borders. Nothing screams "blog post"; the goal is a
 * consultable, print-friendly document.
 */
export function ReportMarkdown({ source }: { source: string }) {
  return (
    <div className="max-w-none overflow-visible break-words text-[0.925rem] leading-7 text-slate-700 [overflow-wrap:anywhere]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => (
            <h1
              className="!mt-8 !mb-3 !text-2xl !leading-tight !font-semibold !tracking-normal !text-slate-950 first:!mt-0"
              {...props}
            />
          ),
          h2: (props) => (
            <h2
              className="!mt-8 !mb-2 !text-lg !leading-snug !font-semibold !tracking-normal !text-slate-900 first:!mt-0"
              {...props}
            />
          ),
          h3: (props) => (
            <h3
              className="!mt-5 !mb-1.5 !text-base !font-semibold !tracking-normal !text-slate-900 first:!mt-0"
              {...props}
            />
          ),
          h4: (props) => (
            <h4
              className="!mt-3 !mb-1 !text-sm !font-medium !tracking-normal first:!mt-0"
              {...props}
            />
          ),
          p: (props) => <p className="my-2 whitespace-normal" {...props} />,
          ul: (props) => (
            <ul className="my-2 list-disc space-y-1 pl-5" {...props} />
          ),
          ol: (props) => (
            <ol className="my-2 list-decimal space-y-1 pl-5" {...props} />
          ),
          li: (props) => (
            <li className="min-w-0 leading-relaxed break-words" {...props} />
          ),
          a: (props) => (
            <a
              className="text-primary underline underline-offset-2 hover:text-primary/80"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),
          blockquote: (props) => (
            <blockquote className="my-4 bg-slate-100/70 px-4 py-3 text-slate-600" {...props} />
          ),
          code: ({ children, className, ...rest }) => {
            const isBlock = /language-/.test(className ?? "");
            return isBlock ? (
              <code
                className="block overflow-x-auto whitespace-pre-wrap bg-slate-100 px-3 py-2 font-mono text-xs"
                {...rest}
              >
                {children}
              </code>
            ) : (
              <code
                className="bg-slate-100 px-1 py-0.5 font-mono text-[0.85em]"
                {...rest}
              >
                {children}
              </code>
            );
          },
          pre: (props) => <pre className="my-3 overflow-x-auto" {...props} />,
          table: (props) => (
            <div className="my-4 overflow-x-auto">
              <table className="w-full text-xs" {...props} />
            </div>
          ),
          thead: (props) => (
            <thead
              className="bg-slate-100 text-[0.7rem] uppercase tracking-wide text-slate-500"
              {...props}
            />
          ),
          th: (props) => (
            <th
              className="border-b px-2 py-1.5 text-left font-medium"
              {...props}
            />
          ),
          td: (props) => (
            <td
              className="border-b px-2 py-1.5 align-top break-words"
              {...props}
            />
          ),
          hr: () => <hr className="my-4 border-slate-200" />,
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}

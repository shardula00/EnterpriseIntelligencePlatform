import type { RagQueryResult, RagQueryStatus } from '../../api/types'

const STATUS_LABELS: Record<RagQueryStatus, string> = {
  answered: 'Answered',
  insufficient_evidence: 'Insufficient evidence',
  error: 'Error',
}

const STATUS_STYLES: Record<RagQueryStatus, string> = {
  answered: 'bg-emerald-100 text-emerald-700',
  insufficient_evidence: 'bg-slate-100 text-slate-600',
  error: 'bg-red-100 text-red-700',
}

/** Renders one answered question: the grounded answer text, plus every
 * cited source chunk (see app/rag/service.py's _to_sources) - never just
 * the answer alone, so a claim is always traceable back to the document,
 * page/section, and similarity score that produced it. */
export function RagAnswerView({ result }: { result: RagQueryResult }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">Answer</h3>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[result.status]}`}
        >
          {STATUS_LABELS[result.status]}
        </span>
      </div>

      <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{result.answer}</p>

      {result.sources.length > 0 && (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sources</h4>
          <ul className="mt-3 flex flex-col gap-3">
            {result.sources.map((source) => (
              <li key={source.chunk_id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <p className="font-medium text-slate-800">📄 {source.filename}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {source.page_number != null && `Page ${source.page_number} · `}
                  {source.section_title && `${source.section_title} · `}
                  Chunk {source.chunk_index} · Score {source.score.toFixed(2)}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

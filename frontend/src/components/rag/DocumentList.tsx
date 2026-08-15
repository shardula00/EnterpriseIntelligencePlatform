import type { DocumentSummary } from '../../api/types'
import { usePermission } from '../../hooks/usePermission'
import { EmptyState } from '../common/EmptyState'
import { DocumentStatusBadge } from './DocumentStatusBadge'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function DocumentList({
  documents,
  onDelete,
  onRetry,
}: {
  documents: DocumentSummary[]
  onDelete: (document: DocumentSummary) => void
  onRetry: (document: DocumentSummary) => void
}) {
  // UX only - the backend independently re-checks rag:upload on
  // delete/process regardless of whether these buttons are shown.
  const canManage = usePermission('rag:upload')

  if (documents.length === 0) {
    return (
      <EmptyState
        title="No documents yet"
        description="Upload a PDF, DOCX, TXT, or Markdown file above to build your enterprise knowledge base."
      />
    )
  }

  return (
    <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
      {documents.map((document) => (
        <li key={document.id} className="flex items-center justify-between gap-4 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">📄 {document.filename}</p>
            <p className="mt-0.5 text-xs text-slate-400">
              {document.status === 'ready' && `${document.chunk_count} chunks · `}
              Uploaded {formatDate(document.created_at)}
            </p>
            {document.status === 'failed' && document.error_message && (
              <p className="mt-1 text-xs text-red-600">{document.error_message}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <DocumentStatusBadge status={document.status} />
            {canManage && document.status === 'failed' && (
              <button
                type="button"
                onClick={() => onRetry(document)}
                className="text-xs font-medium text-accent-600 hover:text-accent-700"
              >
                Retry
              </button>
            )}
            {canManage && (
              <button
                type="button"
                onClick={() => onDelete(document)}
                className="text-xs font-medium text-slate-400 hover:text-red-600"
              >
                Delete
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

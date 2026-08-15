import type { DocumentStatus } from '../../api/types'

const STYLES: Record<DocumentStatus, string> = {
  uploaded: 'bg-slate-100 text-slate-600',
  processing: 'bg-amber-100 text-amber-700',
  ready: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
}

const LABELS: Record<DocumentStatus, string> = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  )
}

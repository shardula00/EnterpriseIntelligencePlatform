import type { LifecycleStatus } from '../../api/types'

const STYLES: Record<LifecycleStatus, string> = {
  candidate: 'bg-slate-100 text-slate-600',
  staging: 'bg-amber-100 text-amber-700',
  production: 'bg-emerald-100 text-emerald-700',
  archived: 'bg-slate-100 text-slate-400',
}

const LABELS: Record<LifecycleStatus, string> = {
  candidate: 'Candidate',
  staging: 'Staging',
  production: 'Production',
  archived: 'Archived',
}

export function LifecycleBadge({ status }: { status: LifecycleStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  )
}

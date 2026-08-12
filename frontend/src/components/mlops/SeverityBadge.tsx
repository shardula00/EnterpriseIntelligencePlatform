import type { MonitoringSeverity } from '../../api/types'

const STYLES: Record<MonitoringSeverity, string> = {
  info: 'bg-slate-100 text-slate-600',
  warning: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

export function SeverityBadge({ severity }: { severity: MonitoringSeverity }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${STYLES[severity]}`}>
      {severity}
    </span>
  )
}

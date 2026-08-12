import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listMonitoringEvents } from '../../api/client'
import type { MonitoringSeverity } from '../../api/types'
import { MonitoringEventList } from '../../components/mlops/MonitoringEventList'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { useAsync } from '../../hooks/useAsync'

const SEVERITY_OPTIONS: (MonitoringSeverity | '')[] = ['', 'critical', 'warning', 'info']

export function MonitoringEventsPage() {
  const [severity, setSeverity] = useState<MonitoringSeverity | ''>('')
  const events = useAsync(
    () => listMonitoringEvents(severity ? { severity } : {}),
    [severity],
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/mlops" className="text-xs font-medium text-accent-600 hover:underline">
          &larr; Back to model registry
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-slate-900">Monitoring Alerts</h1>
        <p className="mt-1 text-sm text-slate-500">
          Every drift and performance check ever run, across every model version, most recent
          first.
        </p>
      </div>

      <label className="text-sm">
        <span className="mb-1 block font-medium text-slate-700">Severity</span>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value as MonitoringSeverity | '')}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === '' ? 'All' : s}
            </option>
          ))}
        </select>
      </label>

      {events.status === 'loading' && <LoadingSpinner label="Loading alerts…" />}
      {events.status === 'error' && <ErrorMessage message={events.error} onRetry={events.reload} />}
      {events.status === 'success' && (
        <MonitoringEventList events={events.data} showVersionLink />
      )}
    </div>
  )
}
